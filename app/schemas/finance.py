from pydantic import BaseModel

class AnalyzeRequest(BaseModel):
    query: str
    thread_id: str = "default-thread"
    model_id: str = "llama-3.3-70b-versatile"


class AnalyzeResponse(BaseModel):
    result: str
