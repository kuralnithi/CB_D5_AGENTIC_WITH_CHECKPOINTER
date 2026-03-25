from pydantic import BaseModel

class AnalyzeRequest(BaseModel):
    query: str
    thread_id: str = "default-thread"


class AnalyzeResponse(BaseModel):
    result: str
