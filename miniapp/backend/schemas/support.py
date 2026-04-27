from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


class TicketSummary(BaseModel):
    id: int
    subject: str
    status: str
    created_at: str
    updated_at: str
    last_message_preview: str


class MessageItem(BaseModel):
    id: int
    sender: str
    text: str
    created_at: str


class TicketDetail(BaseModel):
    id: int
    subject: str
    status: str
    created_at: str
    updated_at: str
    messages: list[MessageItem]
