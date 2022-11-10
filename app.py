import configparser

from cs50 import SQL
from flask import Flask, abort, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))

db = SQL("sqlite:///money.db")
# return a list of dic

records = []

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


def view(id):
    reply = ''
    # Parameters for print formatting
    no_width = 3
    desc_width = 20
    amt_width = 6

    reply += 'Here\'s your expense and income records:\n'
    reply += f'{"No.":{no_width}} {"Description":{desc_width}} {"Amount":{amt_width}}\n'
    reply += '=== ==================== ======\n'
    
    rows = db.execute("SELECT * from records WHERE person_id = ?", id)

    for no, record in enumerate(rows, 1):
        reply += f'{no:<{no_width}} {record["description"]:{desc_width}} {record["amount"]:{amt_width}}\n'
        
    reply += '=== ==================== ======\n'

    balance = 0
    # Sum up the amount of money of records
    for record in rows:
        balance += int(record["amount"])
    
    reply += f'Now you have {balance} dollars.'

    return reply


def add(id, record):
    try:
        desc, amt = record.split()
    except ValueError:
        # If the input string cannot be split into a list of two strings
        return 'The format of a record should be like this: breakfast -50.\nFail to add a record.'
    
    try:
        amt = int(amt) # Check if amt is a numberic string and convert it
    except ValueError:
        # If amt cannot be converted to integer
        return 'Invalid value for money.\nFail to add a record.'
    else:
        # Keep records a list of lists of strings for future str operations
        db.execute("INSERT INTO records (person_id, description, amount) VALUES(?, ?, ?)", id, desc, amt)

        return f'Successfully add a record: {record}'


def delete(id, wanna_del):
    return 'no func'
    try:
        wanna_del = int(wanna_del)
        assert 0 <= wanna_del <= len(records) # Ensure that the input is within the bounds
        
    except ValueError:
        # If the input cannot be converted into an integer
        return 'Invalid format. Fail to delete a record.'
        
    except AssertionError:
        # If the input is out of bounds
        return f'There\'s no record with No.{wanna_del}. Fail to delete a record.'
        
    else:
        if wanna_del == 0: # Do nothing if the input is 0
            return 'The deletion is skipped.'
        
        wanna_del -= 1 # Need adjustment becuase No. is 1 based and the index is 0 based
        # Pop the record
        deleted_desc, deleted_amt = records.pop(wanna_del)

        return f'Successfully delete a record: {deleted_desc} {deleted_amt}'


def update_status(id, new_status):
    db.execute("UPDATE people SET status = ? WHERE id = ?", new_status, id)


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global state

    text = event.message.text
    reply = ''

    user_id = event.source.user_id
    rows = db.execute("SELECT * FROM people WHERE id = ?", user_id)
    if len(rows) == 0:
        db.execute("INSERT INTO people (id, status) VALUES (?, ?)", user_id, 'INIT')
    
    rows = db.execute("SELECT status FROM people WHERE id = ?", user_id)
    user_status = rows[0]['status']

    if user_status == 'INIT':
        if text == 'add':
            reply = "Add an expense or income record with description and amount: "
            update_status(user_id, 'ADD')

        elif text == 'view':
            reply = view(user_id)

        elif text == 'delete':
            reply = "Which record do you want to delete (0 to skip): No.?"
            update_status(user_id, 'DELETE')

        else:
            reply = "Invalid command. Try again."
            update_status(user_id, 'INIT')

    elif user_status == 'ADD':
        reply = add(user_id, text)
        update_status(user_id, 'INIT')

    elif user_status == 'DELETE':
        reply = delete(user_id, text)
        update_status(user_id, 'INIT')

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )


if __name__ == "__main__":
    app.run()