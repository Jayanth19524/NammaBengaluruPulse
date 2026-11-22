"""Entry-point: uvicorn main:app"""
import os
import uvicorn
from tripcast.api import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8003)), reload=False)
