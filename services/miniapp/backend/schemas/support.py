from pydantic import BaseModel, Field, field_validator


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


    @field_validator("subject", "message", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class TicketMetadata(BaseModel):
    category: str = "other"
    context: dict = Field(default_factory=dict)
    last_sender: str = "user"
    waiting_since: str | None = None
    unread: bool = False
    last_message_id: int = 0
    can_reopen: bool = False


class TicketSummary(TicketMetadata):
    id: int
    subject: str
    status: str
    created_at: str
    updated_at: str
    last_message_preview: str


class AttachmentOut(BaseModel):
    id: int
    filename: str
    mime_type: str
    size_bytes: int
    url: str


class MessageItem(BaseModel):
    id: int
    sender: str
    text: str
    created_at: str
    attachments: list[AttachmentOut] = []


class TicketDetail(TicketMetadata):
    id: int
    subject: str
    status: str
    created_at: str
    updated_at: str
    messages: list[MessageItem]
