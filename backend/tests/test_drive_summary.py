import asyncio
import sys
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import platform_core.google_drive_workspace as gw
from types import SimpleNamespace

async def test():
    # Simulate a file content read
    extracted = "Q1. Question One content here.\nQ2. Question Two content here.\n" * 100
    file_name = "TCS-NQT-13th-September-2021-Slot-1-Question-Paper.pdf"
    request = SimpleNamespace(model=None)
    
    print('Testing _summarize_drive_text...')
    summary = await gw._summarize_drive_text(
        None, 
        file_name, 
        "give me the summary of the TCS-NQT-13th-September-2021-Slot-1-Question-Paper.pdf", 
        extracted
    )
    print("SUMMARY RESULT:", summary)

if __name__ == '__main__':
    asyncio.run(test())
