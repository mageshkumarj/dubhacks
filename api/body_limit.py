"""Reject oversized request bodies while they are read, so a chunked body without Content-Length is capped too."""

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .envelope import STUB_HEADERS, fail


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(scope, receive, send)
            return
        state = {"seen": 0, "over": False, "started": False}

        async def limited_receive() -> Message:
            if state["over"]:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                state["seen"] += len(message.get("body", b""))
                if state["seen"] > self.max_bytes and not state["started"]:
                    state["over"] = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if state["over"]:
                return  # drop whatever the app answers to the truncated body; the 413 is sent instead
            state["started"] = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not state["over"]:
                raise
        if state["over"]:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = fail(f"Request body exceeds {self.max_bytes} bytes", "PAYLOAD_TOO_LARGE")
        await JSONResponse(status_code=413, content=body, headers=STUB_HEADERS)(scope, receive, send)
