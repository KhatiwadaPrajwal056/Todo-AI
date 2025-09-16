import openai
from typing import Dict, Any
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import json
import re

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

class TodoAnalyzer:
    @staticmethod
    def analyze_input(user_input: str) -> Dict[str, Any]:
        """
        Analyze user input using GPT to determine the action and extract relevant information
        """
        prompt = f"""You are an intelligent Todo List Management Assistant. Analyze the user's natural language input and generate a structured response. Understand context and implied actions. 
        Remember, The user can give the very complex instructions or not random query or veg, you need to understand what task is given for.
        Also remember from the query, you need to extract the title of the task.

You must respond with ONLY a valid JSON object (no other text).

User Input: "{user_input}"

Response Format:
{{
    "action": "<action_type>",
    "ui_action": "<ui_update_type>",
    "todos": [
        {{
            "title": "task title",
            "description": "task description or null",
            "due_date": "YYYY-MM-DD HH:mm:ss or null",
            "due_in_hours": number or null,
            "priority": 1|2|3,
            "category": "category name or null"
        }}
    ],
    "filters": {{
        "completed": true|false|null,
        "category": "category name or null",
        "priority": 1|2|3|null,
        "due_date_before": "YYYY-MM-DD or null",
        "due_date_after": "YYYY-MM-DD or null"
    }},
    "view_options": {{
        "sort_by": "priority|due_date|created_at|null",
        "sort_order": "asc|desc|null",
        "show_completed": true|false|null
    }}
}}

Action Types:
1. "create" - Create a new todo (Keywords: need to, have to, should, must, want to, going to)
2. "update" - Update/modify/change existing todo
3. "delete" - Delete/remove todo
4. "query" - List/filter/show/find todos
5. "mark_complete" - Mark as done/finished/completed/ready
6. "mark_incomplete" - Mark as not done/pending/incomplete
7. "list_all" - Show all todos

Task Extraction Examples:
- "Need to buy groceries" → create, title="Buy Groceries"
- "Have to finish report by tomorrow" → create with due_date
- "Already completed the report" → mark_complete for "report"
- "Need to change meeting to presentation" → update "meeting" to "presentation"
- "Can't do the gym today" → mark_incomplete for "gym"
- "Get rid of dentist appointment" → delete "dentist appointment"
- "Support need to buy veggies" → create, title="Buy Veggies"

UI Action Types:
1. "refresh_list" - Refresh the entire todo list
2. "add_item" - Add new item to the list
3. "remove_item" - Remove item from the list
4. "update_item" - Update existing item
5. "clear_list" - Clear the list
6. "show_filtered" - Show filtered results
7. "highlight_item" - Highlight specific item

Understanding Natural Language:

1. Creation Patterns:
   - "Need to X" → create task "X"
   - "Have to X" → create task "X"
   - "Should X" → create task "X"
   - "Must X" → create task "X"
   - "Going to X" → create task "X"
   - "Want to X" → create task "X"
   - "Support need to X" → create task "X"
   - "X for tomorrow" → create task "X" with due_date

2. Completion Patterns:
   - "X is done" → mark_complete for "X"
   - "Finished X" → mark_complete for "X"
   - "Completed X" → mark_complete for "X"
   - "X is ready" → mark_complete for "X"
   - "Already X" → mark_complete for "X"

3. Incomplete Patterns:
   - "Can't do X" → mark_incomplete for "X"
   - "Not done with X" → mark_incomplete for "X"
   - "Still need to X" → mark_incomplete for "X"
   - "X is pending" → mark_incomplete for "X"

4. Update/Change Patterns:
   - "Change X to Y" → update task "X" to "Y"
   - "Rename X to Y" → update task "X" to "Y"
   - "Update X to Y" → update task "X" to "Y"
   - "X should be Y" → update task "X" to "Y"

5. Delete Patterns:
   - "Remove X" → delete task "X"
   - "Delete X" → delete task "X"
   - "Get rid of X" → delete task "X"
   - "Cancel X" → delete task "X"
   - "Don't need X anymore" → delete task "X"

6. Query Patterns:
   - "Show X" → query tasks matching "X"
   - "Find X" → query tasks matching "X"
   - "List X" → query tasks matching "X"
   - "What X" → query tasks matching "X"
   - "Any X" → query tasks matching "X"

Priority Levels:
1 = Low
2 = Medium
3 = High

Remember:
1. Always include all required fields
2. Use null for missing/unspecified values
3. Dates must be in YYYY-MM-DD format
4. Return ONLY the JSON object, no additional text"""
        
        try:
            
            # Use GPT-4 for better natural language understanding
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a precise todo list analyzer that excels at extracting tasks from natural language.

                        Important things to remember:
                            Remember, The user can give the very complex instructions or not random query or veg, you need to understand what task is given for.
                            Also remember from the query, you need to extract the title of the task.
                                            
                        Critical Rules:
                        1. For NEW tasks:
                           - Keep important context (location, person, specific details)
                           - Example: "need to meet friend at labim mall" → "Meet Friend at Labim Mall"
                           - Example: "have to buy groceries from walmart" → "Buy Groceries from Walmart"
                        
                        2. For COMPLETED tasks:
                           - Match the exact task as it was created
                           - Example: "met the friend at labim mall" should match "Meet Friend at Labim Mall"
                           - Example: "bought groceries from walmart" should match "Buy Groceries from Walmart"
                        
                        3. Time Handling:
                           - Preserve time information in structured format
                           - Example: "meet john in 2hrs at cafe" → title: "Meet John at Cafe", due_in_hours: 2
                           - Example: "meeting in 2hrs" → title: "Meeting", due_in_hours: 2
                           - Example: "meeting at 2pm or any specific time" → title: "Meeting in 2Pm", due_in_hours: 2PM from now
                           - Example: "tomorrow morning buy milk" → title: "Buy Milk", due_date: [tomorrow morning]
                
                        
                        4. Context Preservation:
                           - Keep locations: "at [place]", "in [location]", "from [place]"
                           - Keep people: "with [person]", "friend", "mom", etc.
                           - Keep specific details that make the task unique
                        
                        5. Title Formatting:
                           - Capitalize each word properly
                           - Keep prepositions (at, in, from, etc.) when they refer to locations
                           - Remove unnecessary words but preserve context
                        
                        Examples of Perfect Handling:
                        Input: "need to meet the friend at labim mall"
                        Output: title: "Meet Friend at Labim Mall"
                        
                        Input: "i met the friend at labim mall"
                        Action: mark_complete
                        Match: "Meet Friend at Labim Mall"
                        
                        Input: "have to buy groceries from walmart today evening"
                        Output: title: "Buy Groceries from Walmart", due_date: [today evening]
                        """
                    },
                    {
                        "role": "user", 
                        "content": prompt + f'\nUser Input: "{user_input}"'
                    }
                ],
                temperature=0
            )
            content = response['choices'][0]['message']['content'].strip()
            try:
                parsed = json.loads(content)
                
                # Handle all actions that require todos array
                if "todos" not in parsed:
                    parsed["todos"] = []
                    
                if parsed.get("action") == "create":
                    if "," in user_input:
                        # Split multiple todos
                        todo_items = [item.strip() for item in user_input.split(",")]
                    else:
                        todo_items = [user_input]
                    
                    todos = []
                    from datetime import datetime, timedelta
                    
                    for item in todo_items:
                        # Get the task details from GPT-4's response
                        todo_data = parsed.get("todos", [{}])[0]
                        title = todo_data.get("title", item.strip())
                        
                        # Preserve original format for matching with completions later
                        title = " ".join(word.capitalize() for word in title.split())
                        
                        # Preserve any additional context from GPT-4's analysis
                        description = todo_data.get("description", title)
                        category = todo_data.get("category")
                        priority = todo_data.get("priority", 1)
                        
                        todo = {
                            "title": title,
                            "description": description,
                            "due_date": todo_data.get("due_date"),
                            "priority": priority,
                            "category": category
                        }

                        # Process time duration for due date
                        time_match = re.search(r'(\d+)\s*(hr|hour|hrs|hours)', item.lower())
                        if time_match:
                            try:
                                hours = int(time_match.group(1))
                                due_time = datetime.now() + timedelta(hours=hours)
                                todo["due_date"] = due_time.strftime("%Y-%m-%d %H:%M:%S")
                                todo["description"] = f"{title.capitalize()} (Due in {hours} hours)"
                            except ValueError:
                                pass
                        
                        todos.append(todo)
                    
                    parsed["todos"] = todos
                    if "ui_action" not in parsed:
                        parsed["ui_action"] = "add_item"
                    
                return parsed
            except json.JSONDecodeError as e:
                print(f"LLM returned invalid JSON, using fallback extraction")
                # Simple fallback - just try to extract a task
                clean_text = user_input.lower()
                
                # Basic cleanup for fallback
                def basic_cleanup(text):
                    # Remove common action and filler words
                    action_words = ["add", "create", "delete", "remove", "update", "change", 
                                  "complete", "finish", "done", "need to", "have to", "must", 
                                  "should", "want to", "going to", "task", "todo"]
                    
                    text = text.lower()
                    for word in action_words:
                        text = re.sub(r'\b' + word + r'\b', '', text)
                    
                    # Clean up whitespace and punctuation
                    text = re.sub(r'\s+', ' ', text).strip()
                    text = re.sub(r'^\W+|\W+$', '', text)
                    return text
                
                # Clean the text and determine action
                task_name = basic_cleanup(clean_text)
                action_word = "create"  # Default to create
                
                # Simple action detection
                if any(word in user_input.lower() for word in ["delete", "remove", "cancel"]):
                    action_word = "delete"
                elif any(word in user_input.lower() for word in ["done", "complete", "finished"]):
                    action_word = "mark_complete"
                
                # Capitalize the task name
                task_name = task_name.strip().capitalize()
                
                if action_word and task_name:
                    return {
                        "action": action_word,
                        "ui_action": "add_item" if action_word == "create" else "update_item",
                        "todos": [{
                            "title": task_name,
                            "description": None,
                            "due_date": None,
                            "priority": 1,
                            "category": None
                        }]
                    }
                return {
                    "action": "error",
                    "error": "Failed to understand the request. Please try again.",
                    "details": str(e)
                }
        except Exception as e:
            print(f"Error analyzing input: {e}")
            return {
                "action": "error",
                "error": "An error occurred while processing your request. Please try again.",
                "details": str(e)
            }