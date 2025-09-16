# TO-DO LLM - Natural Language Task Manager

A smart todo list application that understands natural language inputs and manages your tasks intelligently.

## Features

- **Natural Language Processing**: Create tasks using everyday language
  - "Need to buy groceries"
  - "Have to call mom tomorrow"
  - "Going to write report"
- **Smart Task Extraction**: Automatically extracts the core task from your input
- **Task Management**: Add, complete, and delete tasks easily

## Usage

1. **Adding Tasks**
   - Simply type your task in natural language
   - The system will automatically extract the core task
   - Examples:
     - "Need to buy vegetables" → Creates task "buy vegetables"
     - "Have to clean room" → Creates task "clean room"
     - "Must call mom" → Creates task "call mom"

2. **Managing Tasks**
   - Mark tasks as complete/incomplete
   - Delete tasks when no longer needed


---

## ⚡ Getting Started  

   1. **Clone the repository**  
      ```bash
      git clone https://github.com/KhatiwadaPrajwal056/Todo-AI.git
      cd Todo-AI
   2. **Create a virtual environment**  
      ```bash
      python -m venv venv
      source venv/bin/activate   # On Windows: venv\Scripts\activate
   3. **Create a .env file**  
      ```bash
      OPENAI_API_KEY=your_api_key_here
   4. **Install dependencies**  
      ```bash
      pip install -r requirements.txt
   5. **Run the application**  
      ```bash
      uvicorn app.main:app --reload
   6. **Open your browser**  
      ```bash
      Navigate to http://localhost:8000