from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, database, auth
from .llm_processor import TodoAnalyzer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

class TodoRequest(BaseModel):
    user_input: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Remove old database file and create new tables
import os
if os.path.exists("todos.db"):
    os.remove("todos.db")

# Create tables and initial users
models.Base.metadata.create_all(bind=database.engine)
auth.create_initial_users(next(database.get_db()))

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Handle authentication in the frontend
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/todos")
async def get_todos(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    """Get all todos for the current user"""
    return get_filtered_todos(db, {}, {}, current_user)

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "username": user.username}

def find_matching_todo(db: Session, title: str, user_id: int):
    """Find a todo by fuzzy matching the title"""
    # Try exact match first
    todo = db.query(models.Todo).filter(
        models.Todo.title.ilike(f"%{title}%"),
        models.Todo.user_id == user_id
    ).first()
    
    if not todo:
        # Try partial match
        title_words = title.lower().split()
        todos = db.query(models.Todo).filter(
            models.Todo.user_id == user_id
        ).all()
        
        for t in todos:
            todo_title = t.title.lower()
            if any(word in todo_title for word in title_words):
                return t
    
    return todo

@app.post("/process")
async def process_input(
    todo_request: TodoRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        # Analyze user input using LLM
        analysis = TodoAnalyzer.analyze_input(todo_request.user_input)
        
        if not analysis:
            return {"todos": [], "error": "Failed to process your request. Please try again."}
        
        if analysis.get("action") == "error":
            return {"todos": [], "error": analysis.get("error", "Unknown error occurred")}
            
        if "action" not in analysis:
            analysis["action"] = "create"
            analysis["todo_info"] = {
                "title": todo_request.user_input,
                "description": None,
                "due_date": None,
                "priority": 1,
                "category": None
            }
    except Exception as e:
        return {"todos": [], "error": f"Failed to process request: {str(e)}"}
    
    if analysis["action"] == "create":
        try:
            # Log the analysis for debugging
            print(f"Analysis: {analysis}")
            # Handle multiple todos from the analysis
            todos_to_create = analysis.get("todos", [])
            if not todos_to_create and "todo_info" in analysis:
                # Fallback: create single todo from todo_info
                todos_to_create = [{
                    "title": analysis["todo_info"]["title"],
                    "description": analysis["todo_info"]["description"],
                    "due_date": analysis["todo_info"]["due_date"],
                    "priority": analysis["todo_info"]["priority"]
                }]
            elif not todos_to_create:
                todos_to_create = [{
                    "title": todo_request.user_input,
                    "description": todo_request.user_input,
                    "due_date": None,
                    "priority": 1
                }]
            
            # Create all todos
            for todo_info in todos_to_create:
                todo = models.Todo(
                    title=todo_info["title"],
                    description=todo_info.get("description"),
                    user_id=current_user.id,
                    priority=todo_info.get("priority", 1),
                    completed=False
                )
                
                # Handle due date if present
                if todo_info.get("due_date"):
                    todo.due_date = datetime.strptime(todo_info["due_date"], "%Y-%m-%d %H:%M:%S")
                
                db.add(todo)
            
            db.commit()
            
            todos = get_filtered_todos(db, {}, {}, current_user)
            count = len(todos_to_create)
            todos["message"] = f"Created {count} {'todo' if count == 1 else 'todos'} successfully"
            return todos
            
        except Exception as e:
            print(f"Error creating todo: {str(e)}")
            db.rollback()
            return {"todos": [], "error": "Failed to create todo. Please try again."}
    
    elif analysis["action"] in ["mark_complete", "mark_incomplete"]:
        # Update todo completion status
        print(f"Processing completion status: {analysis}")
        todos = analysis.get("todos", [])
        if not todos:
            print("No todos found in analysis")
            if "todo_info" in analysis:
                todo_title = analysis["todo_info"]["title"]
            else:
                # Extract title from user input for completion
                user_input = todo_request.user_input.lower()
                words_to_remove = ["mark", "as", "complete", "completed", "incomplete", "done", "todo", "task"]
                for word in words_to_remove:
                    user_input = user_input.replace(word, "")
                todo_title = user_input.strip().capitalize()
        else:
            todo_title = todos[0]["title"]

        print(f"Looking for todo with title: {todo_title}")
        todo = find_matching_todo(db, todo_title, current_user.id)
        
        if not todo:
            print(f"Todo not found with title: {todo_title}")
            raise HTTPException(status_code=404, detail=f"Todo not found: {todo_title}")
        
        todo.completed = analysis["action"] == "mark_complete"
        db.commit()
        return get_todos_response(db, f"Todo marked as {analysis['action'].replace('mark_', '')}", current_user)
    
    elif analysis["action"] == "update":
        # Update existing todo
        todo_info = analysis["todo_info"]
        todo = db.query(models.Todo).filter(models.Todo.title == todo_info["title"]).first()
        if not todo:
            raise HTTPException(status_code=404, detail="Todo not found")
        
        # Update fields
        for key, value in todo_info.items():
            if value is not None and hasattr(todo, key):
                if key == "due_date" and value:
                    value = datetime.fromisoformat(value)
                setattr(todo, key, value)
        
        db.commit()
        return get_todos_response(db, "Todo updated successfully", current_user)

    elif analysis["action"] == "update":
        # Update todo title
        todos = analysis.get("todos", [])
        if not todos or len(todos) < 2:
            raise HTTPException(status_code=400, detail="Missing update information")
            
        old_title = todos[0]["title"]
        new_title = todos[1]["title"]
        
        # Find and update the todo
        todo = find_matching_todo(db, old_title, current_user.id)
        if not todo:
            raise HTTPException(status_code=404, detail=f"Todo not found: {old_title}")
        
        # Check if new title already exists
        existing = db.query(models.Todo).filter(
            models.Todo.title == new_title,
            models.Todo.user_id == current_user.id,
            models.Todo.id != todo.id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="A todo with this title already exists")
        
        todo.title = new_title
        db.commit()
        return get_todos_response(db, "Todo updated successfully", current_user)

    elif analysis["action"] in ["query", "list_all"]:
        # Query todos
        view_options = analysis.get("view_options", {})
        return get_filtered_todos(db, analysis.get("filters", {}), view_options, current_user)
    
    elif analysis["action"] == "delete":
        # Delete todo
        print(f"Processing deletion: {analysis}")
        todos = analysis.get("todos", [])
        if not todos:
            print("No todos found in analysis")
            if "todo_info" in analysis:
                todo_title = analysis["todo_info"]["title"]
            else:
                # Extract title from user input for deletion
                user_input = todo_request.user_input.lower()
                words_to_remove = ["delete", "remove", "todo", "task"]
                for word in words_to_remove:
                    user_input = user_input.replace(word, "")
                todo_title = user_input.strip().capitalize()
        else:
            todo_title = todos[0]["title"]

        print(f"Looking for todo with title: {todo_title}")
        todo = find_matching_todo(db, todo_title, current_user.id)
        
        if not todo:
            print(f"Todo not found with title: {todo_title}")
            raise HTTPException(status_code=404, detail=f"Todo not found: {todo_title}")
        
        db.delete(todo)
        db.commit()
        return get_todos_response(db, "Todo deleted successfully", current_user)
    
    raise HTTPException(status_code=400, detail="Invalid action")

def get_todos_response(db: Session, message: str = None, current_user: models.User = None):
    """Helper function to return todos along with a message"""
    todos = get_filtered_todos(db, {}, {}, current_user)
    if message:
        todos["message"] = message
    return todos

def get_filtered_todos(db: Session, filters: dict, view_options: dict, current_user: models.User = None):
    """Get filtered and sorted todos based on filters and view options"""
    try:
        if not current_user:
            return {"todos": [], "message": "Please log in to view todos"}

        query = db.query(models.Todo)
        
        # Always filter by user unless it's an admin
        if not current_user.is_admin:
            query = query.filter(models.Todo.user_id == current_user.id)
            
        # Get todos and convert to dict
        todos = query.all()
        return {
            "todos": [
                {
                    "id": todo.id,
                    "title": todo.title,
                    "description": todo.description,
                    "completed": todo.completed,
                    "priority": todo.priority,
                    "due_date": todo.due_date.isoformat() if todo.due_date else None,
                    "category": todo.category.name if todo.category else None,
                }
                for todo in todos
            ]
        }
    except Exception as e:
        print(f"Error in get_filtered_todos: {str(e)}")
        return {"todos": [], "error": "Failed to fetch todos"}
    
    # Apply filters