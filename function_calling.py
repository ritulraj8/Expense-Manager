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

def add_income(amount: float, account: str, category: str, narration: str = None, date: str = None):
    """
    Add an income transaction.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    if not narration:
        narration = f"Income of ${amount} to {account} under category {category}"
    conn = sqlite3.connect("ritul.db")
    cursor = conn.cursor()
    try:
        debit_acc_id = None
        credit_acc_id = get_or_create_account(cursor, account)
        cat_id = get_or_create_category(cursor, category, "income")
        cursor.execute("""
            INSERT INTO TRANSACTIONS (type, transaction_date, debit_account_id, credit_account_id, income_category_id, amount, narration)
            VALUES ('income', ?, ?, ?, ?, ?, ?)
        """, (date, debit_acc_id, credit_acc_id, cat_id, amount, narration))
        conn.commit()
        return {
            "status": "success",
            "message": f"Added income transaction of ${amount} to {account} under category {category}."
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def add_expense(amount: float, account: str, category: str, narration: str = None, date: str = None):
    """
    Add an expense transaction.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    if not narration:
        narration = f"Expense of ${amount} from {account} under category {category}"
    conn = sqlite3.connect("ritul.db")
    cursor = conn.cursor()
    try:
        debit_acc_id = get_or_create_account(cursor, account)
        credit_acc_id = None
        cat_id = get_or_create_category(cursor, category, "expense")
        cursor.execute("""
            INSERT INTO TRANSACTIONS (type, transaction_date, debit_account_id, credit_account_id, expense_category_id, amount, narration)
            VALUES ('expense', ?, ?, ?, ?, ?, ?)
        """, (date, debit_acc_id, credit_acc_id, cat_id, amount, narration))
        conn.commit()
        return {
            "status": "success",
            "message": f"Added expense transaction of ${amount} from {account} under category {category}."
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def add_transfer(amount: float, from_account: str, to_account: str, narration: str = None, date: str = None):
    """
    Add a transfer transaction.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    if not narration:
        narration = f"Transfer of ${amount} from {from_account} to {to_account}"
    conn = sqlite3.connect("ritul.db")
    cursor = conn.cursor()
    try:
        debit_acc_id = get_or_create_account(cursor, to_account)
        credit_acc_id = get_or_create_account(cursor, from_account)
        cursor.execute("""
            INSERT INTO TRANSACTIONS (type, transaction_date, debit_account_id, credit_account_id, amount, narration)
            VALUES ('transfer', ?, ?, ?, ?, ?)
        """, (date, debit_acc_id, credit_acc_id, amount, narration))
        conn.commit()
        return {
            "status": "success",
            "message": f"Transferred ${amount} from {from_account} to {to_account}."
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