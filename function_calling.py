from huggingface_hub import hf_hub_download
from llama_cpp import Llama
import json
import sqlite3
import re
from datetime import datetime
# ---------------------------
# Model Loading
# ---------------------------

def load_model():
    model_path = hf_hub_download(
        repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
        filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf"
    )

    return Llama(
        model_path=model_path,
        n_ctx=8192,
        n_gpu_layers=-1,
        verbose=False
    )


# ---------------------------
# Database Helpers
# ---------------------------

def get_or_create_account(cursor, name):
    cursor.execute("SELECT id FROM ACCOUNTS WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO ACCOUNTS (name, open_balance) VALUES (?, 0.0)", (name,))
    return cursor.lastrowid


def find_account_case_insensitive(cursor, name):
    if not name:
        return None, None
    name = str(name).strip()
    # Try exact case-insensitive match
    cursor.execute("SELECT id, name FROM ACCOUNTS WHERE LOWER(name) = ?", (name.lower(),))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    
    # Try substring match
    cursor.execute("SELECT id, name FROM ACCOUNTS")
    all_accounts = cursor.fetchall()
    for acc_id, acc_name in all_accounts:
        acc_name_lower = acc_name.lower()
        name_lower = name.lower()
        if acc_name_lower in name_lower or name_lower in acc_name_lower:
            return acc_id, acc_name
            
    return None, None


def get_word_root(word):
    word = word.lower().strip()
    if word.endswith('ies') and len(word) > 3:
        return word[:-3] + 'y'
    for suffix in ['ing', 'ed', 'es', 's']:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            return word[:-len(suffix)]
    return word


def find_category_case_insensitive(cursor, name, type_):
    if not name:
        return None, None
    name = str(name).strip()
    lower_name = name.lower()
    
    # Try exact case-insensitive match
    cursor.execute("SELECT id, name FROM CATEGORY WHERE LOWER(name) = ? AND type = ?", (name.lower(), type_))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
                    
    # 2. Word-level Root/Stem Match
    cursor.execute("SELECT id, name FROM CATEGORY WHERE type = ?", (type_,))
    all_categories = cursor.fetchall()
    
    input_words = [get_word_root(w) for w in re.findall(r'\w+', lower_name) if len(w) > 1]
    
    for cat_id, cat_name in all_categories:
        cat_words = [get_word_root(w) for w in re.findall(r'\w+', cat_name.lower()) if len(w) > 1]
        
        # Check if any input root word matches any category root word
        for iw in input_words:
            if iw in cat_words:
                return cat_id, cat_name
                
    # 3. Substring match fallback
    for cat_id, cat_name in all_categories:
        cat_name_lower = cat_name.lower()
        if cat_name_lower in lower_name or lower_name in cat_name_lower:
            return cat_id, cat_name
            
    return None, None


def get_or_create_category(cursor, name, type_):
    cursor.execute("SELECT id FROM CATEGORY WHERE name = ? AND type = ?", (name, type_))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO CATEGORY (type, name) VALUES (?, ?)", (type_, name))
    return cursor.lastrowid


# ---------------------------
# Tools
# ---------------------------

def add_income(amount: float = None, account: str = None, category: str = None, narration: str = None, date: str = None):
    """
    Add an income transaction.
    """
    try:
        if amount is not None:
            amount = float(amount)
    except (ValueError, TypeError):
        amount = None

    missing_fields = []
    
    if not date:
        missing_fields.append("date")
        
    if amount is None or amount <= 0:
        missing_fields.append("amount")
        
    db_account_name = None
    if not account:
        missing_fields.append("credited account")
    else:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        acc_id, db_account_name = find_account_case_insensitive(cursor, account)
        conn.close()
        if not acc_id:
            db_account_name = account.strip()
            
    db_category_name = None
    if not category:
        missing_fields.append("income category")
    else:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        cat_id, db_category_name = find_category_case_insensitive(cursor, category, "income")
        conn.close()
        if not cat_id:
            db_category_name = category.strip()
            
    if missing_fields:
        return {
            "status": "error",
            "message": f"Validation Error: Could not determine mandatory fields: {', '.join(missing_fields)}"
        }
        
    if not narration:
        narration = f"Income of ${amount} to {db_account_name} under category {db_category_name}"
        
    conn = sqlite3.connect("ritul.db")
    cursor = conn.cursor()
    try:
        debit_acc_id = None
        credit_acc_id = get_or_create_account(cursor, db_account_name)
        cat_id = get_or_create_category(cursor, db_category_name, "income")
        cursor.execute("""
            INSERT INTO TRANSACTIONS (type, transaction_date, debit_account_id, credit_account_id, income_category_id, amount, narration)
            VALUES ('income', ?, ?, ?, ?, ?, ?)
        """, (date, debit_acc_id, credit_acc_id, cat_id, amount, narration))
        conn.commit()
        return {
            "status": "success",
            "message": f"Added income transaction of ${amount} to {db_account_name} under category {db_category_name}."
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def add_expense(amount: float = None, account: str = None, category: str = None, narration: str = None, date: str = None):
    """
    Add an expense transaction.
    """
    try:
        if amount is not None:
            amount = float(amount)
    except (ValueError, TypeError):
        amount = None

    missing_fields = []
    
    if not date:
        missing_fields.append("date")
        
    if amount is None or amount <= 0:
        missing_fields.append("amount")
        
    db_account_name = None
    if not account:
        missing_fields.append("debited account")
    else:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        acc_id, db_account_name = find_account_case_insensitive(cursor, account)
        conn.close()
        if not acc_id:
            db_account_name = account.strip()
            
    db_category_name = None
    if not category:
        missing_fields.append("expense category")
    else:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        cat_id, db_category_name = find_category_case_insensitive(cursor, category, "expense")
        conn.close()
        if not cat_id:
            db_category_name = category.strip()
            
    if missing_fields:
        return {
            "status": "error",
            "message": f"Validation Error: Could not determine mandatory fields: {', '.join(missing_fields)}"
        }
        
    if not narration:
        narration = f"Expense of ${amount} from {db_account_name} under category {db_category_name}"
        
    conn = sqlite3.connect("ritul.db")
    cursor = conn.cursor()
    try:
        debit_acc_id = get_or_create_account(cursor, db_account_name)
        credit_acc_id = None
        cat_id = get_or_create_category(cursor, db_category_name, "expense")
        cursor.execute("""
            INSERT INTO TRANSACTIONS (type, transaction_date, debit_account_id, credit_account_id, expense_category_id, amount, narration)
            VALUES ('expense', ?, ?, ?, ?, ?, ?)
        """, (date, debit_acc_id, credit_acc_id, cat_id, amount, narration))
        conn.commit()
        return {
            "status": "success",
            "message": f"Added expense transaction of ${amount} from {db_account_name} under category {db_category_name}."
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def add_transfer(amount: float = None, from_account: str = None, to_account: str = None, narration: str = None, date: str = None):
    """
    Add a transfer transaction.
    """
    try:
        if amount is not None:
            amount = float(amount)
    except (ValueError, TypeError):
        amount = None

    missing_fields = []
    
    if not date:
        missing_fields.append("date")
        
    if amount is None or amount <= 0:
        missing_fields.append("amount")
        
    db_from_account = None
    if not from_account:
        missing_fields.append("credited account")
    else:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        acc_id, db_from_account = find_account_case_insensitive(cursor, from_account)
        conn.close()
        if not acc_id:
            db_from_account = from_account.strip()
            
    db_to_account = None
    if not to_account:
        missing_fields.append("debited account")
    else:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        acc_id, db_to_account = find_account_case_insensitive(cursor, to_account)
        conn.close()
        if not acc_id:
            db_to_account = to_account.strip()
            
    if missing_fields:
        return {
            "status": "error",
            "message": f"Validation Error: Could not determine mandatory fields: {', '.join(missing_fields)}"
        }
        
    if not narration:
        narration = f"Transfer of ${amount} from {db_from_account} to {db_to_account}"
        
    conn = sqlite3.connect("ritul.db")
    cursor = conn.cursor()
    try:
        debit_acc_id = get_or_create_account(cursor, db_from_account)
        credit_acc_id = get_or_create_account(cursor, db_to_account)
        cursor.execute("""
            INSERT INTO TRANSACTIONS (type, transaction_date, debit_account_id, credit_account_id, amount, narration)
            VALUES ('transfer', ?, ?, ?, ?, ?)
        """, (date, debit_acc_id, credit_acc_id, amount, narration))
        conn.commit()
        return {
            "status": "success",
            "message": f"Transferred ${amount} from {db_from_account} to {db_to_account}."
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


available_functions = {
    "add_income": add_income,
    "add_expense": add_expense,
    "add_transfer": add_transfer
}


tools = [
    {
        "type": "function",
        "function": {
            "name": "add_income",
            "description": "Add an income transaction when money is received.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The amount of income received."
                    },
                    "account": {
                        "type": "string",
                        "description": "The bank/wallet account name where the money went (e.g. 'City Bank')."
                    },
                    "category": {
                        "type": "string",
                        "description": "The income category (e.g. 'Sales')."
                    },
                    "narration": {
                        "type": "string",
                        "description": "A description of the transaction (e.g. 'selling pocket computer')."
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date of transaction in YYYY-MM-DD format."
                    }
                },
                "required": ["amount", "account", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Add an expense transaction when money is spent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The amount spent."
                    },
                    "account": {
                        "type": "string",
                        "description": "The bank/wallet account name from which money was paid (e.g. 'Wallet')."
                    },
                    "category": {
                        "type": "string",
                        "description": "The expense category (e.g. 'Food')."
                    },
                    "narration": {
                        "type": "string",
                        "description": "A description of the transaction."
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date of transaction in YYYY-MM-DD format."
                    }
                },
                "required": ["amount", "account", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_transfer",
            "description": "Add a transfer transaction between accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The amount transferred."
                    },
                    "from_account": {
                        "type": "string",
                        "description": "The source account name."
                    },
                    "to_account": {
                        "type": "string",
                        "description": "The destination account name."
                    },
                    "narration": {
                        "type": "string",
                        "description": "A description of the transfer."
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date of transfer in YYYY-MM-DD format."
                    }
                },
                "required": ["amount", "from_account", "to_account"]
            }
        }
    }
]


# ---------------------------
# Tool Execution Loop
# ---------------------------

def has_date(text):
    if not isinstance(text, str):
        return False
    # Check for YYYY-MM-DD or DD/MM/YYYY or MM/DD/YYYY
    if re.search(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', text):
        return True
    if re.search(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', text):
        return True

    # Check for month names (e.g. June, Jun, etc.)
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
    ]
    for month in months:
        if re.search(r'\b' + month + r'\b', text, re.IGNORECASE):
            return True

    # Check for relative date terms
    relative_terms = ["today", "yesterday", "tomorrow", "tonight"]
    for term in relative_terms:
        if re.search(r'\b' + term + r'\b', text, re.IGNORECASE):
            return True

    # Check for days of the week
    days = [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "mon", "tue", "wed", "thu", "fri", "sat", "sun"
    ]
    for day in days:
        if re.search(r'\b' + day + r'\b', text, re.IGNORECASE):
            return True

    # Check for ordinal days (e.g., 24th, 1st, 2nd, 3rd)
    if re.search(r'\b\d{1,2}(st|nd|rd|th)\b', text, re.IGNORECASE):
        return True

    return False


def run_tool_calls(llm, messages):
    has_system = any(msg.get("role") == "system" for msg in messages)
    if not has_system:
        income_cats = []
        expense_cats = []
        existing_accounts = []
        try:
            conn = sqlite3.connect("ritul.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM CATEGORY WHERE type = 'income'")
            income_cats = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT name FROM CATEGORY WHERE type = 'expense'")
            expense_cats = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT name FROM ACCOUNTS")
            existing_accounts = [row[0] for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            print("Error fetching database context for prompt:", e)

        system_content = (
            "You are a precise financial transaction assistant. Categorize user transactions to the correct tool:\n"
            "- `add_income`: Use when money is received/earned/got.\n"
            "  Example user prompts:\n"
            "  * 'Got $2000 for software sales into Federal Bank' -> call add_income(amount=2000, account='Federal Bank', category='sales')\n"
            "  * 'received $50 salary in Cash' -> call add_income(amount=50, account='Cash', category='Salary')\n"
            "- `add_expense`: Use when money is paid/spent/given (e.g. wages paid, buying items).\n"
            "  Example user prompts:\n"
            "  * 'Paid wages of $100 to daily workers from SBI' -> call add_expense(amount=100, account='SBI', category='Wages')\n"
            "  * 'spent $10 on coffee from Kotak Bank' -> call add_expense(amount=10, account='Kotak Bank', category='Coffee')\n"
            "- `add_transfer`: Use when transferring money between two accounts.\n"
            "  Example user prompt: 'transfer $200 from canara to sbi' -> call add_transfer(amount=200, from_account='canara', to_account='sbi')\n\n"
        )
        
        if existing_accounts:
            system_content += f"Existing accounts in database: {', '.join(existing_accounts)}\n"
        if income_cats:
            system_content += f"Existing income categories in database: {', '.join(income_cats)}\n"
        if expense_cats:
            system_content += f"Existing expense categories in database: {', '.join(expense_cats)}\n"

        system_content += (
            "\nStrict classification and mapping rules:\n"
            "1. Prompts containing 'Paid', 'paid', 'spent', 'spent wages', or 'Paid wages' are strictly EXPENSES. You MUST call `add_expense`.\n"
            "2. Prompts containing 'Got', 'received', 'earned', 'income' are strictly INCOME. You MUST call `add_income`.\n"
            "3. For a transaction to be classified as a transfer (`add_transfer`), BOTH the source (from) and destination (to) accounts must be explicitly mentioned. If only one account is mentioned (e.g. 'transfer $50 from SBI' or 'sent $20 to Kotak Bank'), do NOT call `add_transfer`. Instead, call `add_income` (if the amount is credited to that account) or `add_expense` (if the amount is debited from that account).\n"
            "4. MAPPING RULE: Look at the existing accounts and categories listed above. If the user mentions a category or account that is conceptually the same as one of the existing ones (e.g. 'sold', 'selling', or 'sale of product' maps to 'Sales'; 'wages paid' or 'labor cost' maps to 'Wages'; 'coffee and snacks' or 'tea' maps to 'Coffee'; 'grocery shopping' or 'supermarket' maps to 'Groceries'; 'electricity charge' or 'electric power' maps to 'Electricity'), you MUST use the exact name of the existing account/category from the database. Do NOT create a new name if an existing name covers it."
        )

        messages.insert(0, {
            "role": "system",
            "content": system_content
        })

    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            if not has_date(msg["content"]):
                current_date = datetime.now().strftime("%Y-%m-%d")
                msg["content"] = f"{msg['content']} (Today's date: {current_date})"
                print(f"Date was not present in prompt. Appended today's date: {current_date}")

    while True:

        response = llm.create_chat_completion(
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response["choices"][0]["message"]

        if message.get("tool_calls") is None:
            print("\nFINAL ANSWER:")
            print(message["content"])
            return response

        messages.append(message)

        for tool_call in message["tool_calls"]:

            function_name = tool_call["function"]["name"]

            arguments = json.loads(
                tool_call["function"]["arguments"]
            )

            print(f"\nCalling: {function_name}")
            print("Arguments:", arguments)

            function = available_functions[function_name]

            result = function(**arguments)

            print("Result:", result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": json.dumps(result)
            })


# ---------------------------
# Parse Function Calls
# ---------------------------

def parse_function_calls(content):
    calls = []

    for part in content.split(";"):
        part = part.strip()

        if part:
            calls.append(json.loads(part))

    return calls


# ---------------------------
# Execute Parsed Calls
# ---------------------------

def execute_calls(calls):
    results = []

    for call in calls:

        function_name = call["name"]

        args = call["parameters"]

        result = available_functions[function_name](**args)

        results.append({
            "function": function_name,
            "result": result
        })

    return results


# ---------------------------
# Generate Final Response
# ---------------------------

def generate_final_answer(llm, messages, content, results):

    messages.append({
        "role": "assistant",
        "content": content
    })

    messages.append({
        "role": "user",
        "content": f"Function results:\n{json.dumps(results, indent=2)}\n\nGenerate the final answer."
    })

    final_response = llm.create_chat_completion(
        messages=messages
    )

    return final_response["choices"][0]["message"]["content"]


# ---------------------------
# Prompt Validation Helpers
# ---------------------------

def check_amount_in_prompt(prompt):
    """
    Check if an amount is mentioned in the prompt (excluding year numbers in dates).
    """
    if not isinstance(prompt, str):
        return False
    
    # Remove dates to avoid matching date numbers as amounts
    cleaned = prompt
    cleaned = re.sub(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', ' ', cleaned)
    cleaned = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', ' ', cleaned)
    # Remove standalone years (like 2020-2039, 1900-1999)
    cleaned = re.sub(r'\b(202\d|203\d|19\d\d)\b', ' ', cleaned)
    
    # Check for digits
    if re.search(r'\d+', cleaned):
        return True
        
    # Check for number words
    number_words = [
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety", "hundred", "thousand", "lakh", "million", "crore"
    ]
    prompt_lower = cleaned.lower()
    for word in number_words:
        if re.search(r'\b' + word + r'\b', prompt_lower):
            return True
            
    return False


def check_bank_in_prompt(prompt):
    """
    Check if a bank or account is mentioned in the prompt.
    """
    if not isinstance(prompt, str):
        return False
        
    try:
        conn = sqlite3.connect("ritul.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM ACCOUNTS")
        accounts = [row[0].lower() for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print("Error fetching accounts:", e)
        accounts = []
        
    prompt_lower = prompt.lower()
    
    # General bank/payment terms
    general_terms = ["bank", "wallet", "cash", "account", "card", "online", "gpay", "paytm", "phonepe", "upi"]
    for term in general_terms:
        if term in prompt_lower:
            return True
            
    # Database account names
    for acc in accounts:
        if acc in prompt_lower:
            return True
        # Check individual words of the accounts
        words = acc.split()
        for w in words:
            # ignore generic words and short words
            if w not in ["bank", "by", "cash", "account"] and len(w) > 2:
                if w in prompt_lower:
                    return True
                    
    return False


# ---------------------------
# Main
# ---------------------------

def main():

    llm = load_model()

    messages = [
        {
            "role": "user",
            "content": "I have sent $2000 from Canara bank to SBI bank"
        }
    ]

    response = run_tool_calls(llm, messages)

    content = response["choices"][0]["message"]["content"]

    calls = parse_function_calls(content)
    print(calls)

    results = execute_calls(calls)
    print(results)

    final_answer = generate_final_answer(
        llm,
        messages,
        content,
        results
    )

    print(final_answer)


if __name__ == "__main__":
    main()