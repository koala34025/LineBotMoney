import os
import sys

from cs50 import SQL
from flask import Flask, abort, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

#db = SQL("sqlite:///money.db")
internal_database_url = os.getenv('INTERNAL_DATABASE_URL', None)
external_database_url = os.getenv('EXTERNAL_DATABASE_URL', None)
db = SQL(internal_database_url)
# return a list of dic


commands = [
    'add',
    'view',
    'delete',
    'edit',
    'view categories',
    'find'
]

categories = [
    'expense', 
    [
        'food',
        [
            'meal', 
            'snack', 
            'drink'
        ], 
        'transportation', 
        [
            'bus', 
            'railway'
        ]
    ], 
    'income', 
    [
        'salary', 
        'bonus'
    ]
]


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


def view_categories(categories=categories, level = -1):
    '''Show all the categories, return with a reply list
    '''
    if type(categories) == str:
        return ['  ' * level + '- ' + categories]
    
    reply_list = []
    for e in categories:
        reply_list += view_categories(e, level + 1)
    return reply_list


def is_category_valid(target, categories=categories):
    '''Return if a category is in the category list
    '''
    if type(categories) == str:
        return categories == target
        
    result = False
    for e in categories:
        result |= is_category_valid(target, e)
    return result


def find_subcategories(target, categories=categories):
    '''Return a nested list containing a certain category and its subcategories
    '''
    result = []
    for idx, e in enumerate(categories):
        if type(e) == str:
            if e == target:
                if idx + 1 < len(categories) and type(categories[idx+1]) == list:
                    return categories[idx: idx+2]
                else:
                    return [categories[idx]]
        else:
            result += find_subcategories(target, e)

    return result


def flatten(L):
    '''Flat a nested list
    '''
    if type(L) == str:
        return [L]

    ret = []
    for e in L:
        ret += flatten(e)
    return ret


def find(id, target):
    '''Show all the records under a certain category and its subcategories 
    '''
    reply = ''
    # Parameters for print formatting
    cate_width = 15
    no_width = 3
    desc_width = 20
    amt_width = 6
    
    subcategories = flatten(find_subcategories(target, categories))
    
    if len(subcategories) == 0:
        return 'The specified category is not in the category list.\n' \
        'You can check the category list by command "view categories".\n' \
        'Fail to find category.'

    reply += f'Here\'s your expense and income records under category "{target}":\n'
    reply += f'{"No.":{no_width}} {"Category":{cate_width}} {"Description":{desc_width}} {"Amount":{amt_width}}\n'
    reply += '=== =============== ==================== ======\n'
    
    rows = db.execute("SELECT * from records WHERE person_id = ?", id)
    subrecords = list(filter(lambda record: record["category"] in subcategories, rows))

    for record in subrecords:
        reply += f'{record["record_id"]:<{no_width}} {record["category"]:{cate_width}} {record["description"]:{desc_width}} {record["amount"]:{amt_width}}\n'
        
    reply += '=== =============== ==================== ======\n'

    total = 0
    # Sum up the amount of money of records
    for record in subrecords:
        total += int(record["amount"])
    
    reply += f'The total amount above is {total}.'

    return reply


def edit_ask_for_id(id, wanna_edit, num_of_rec):
    try:
        wanna_edit = int(wanna_edit)
        assert 0 <= wanna_edit <= num_of_rec # Ensure that the input is within the bounds
        
    except ValueError:
        # If the input cannot be converted into an integer
        return 'Invalid format. Fail to edit a record.'
        
    except AssertionError:
        # If the input is out of bounds
        return f'There\'s no record with No.{wanna_edit}. Fail to edit a record.'
        
    if wanna_edit == 0: # Do nothing if the input is 0
        return 'The edit is skipped'
        
    update_request_id(id, wanna_edit)
    return "Edit the record with new category, description, and amount: "


def edit(id, new_record, num_of_rec):
    try:
        cate, desc, amt = new_record.split()
    except ValueError:
        # If the input string cannot be split into a list of two strings
        return 'The format of a record should be like this: meal breakfast -50.\nFail to edit a record.'

    # Handle cate not in categories
    if not is_category_valid(cate):
        return 'The specified category is not in the category list.\n' \
        'You can check the category list by command "view categories".\n' \
        'Fail to edit a record.'

    try:
        amt = int(amt) # Check if amt is a numberic string
    except ValueError:
        # If amt cannot be converted to integer
        return 'Invalid value for money.\nFail to edit a record.'
    
    rows = db.execute("SELECT request_id FROM people WHERE id = ?", id)
    request_id = rows[0]['request_id']
    db.execute("UPDATE records SET category = ?, description = ?, amount = ? WHERE person_id = ? AND record_id = ?", cate, desc, amt, id, request_id)

    return f'Successfully edit a record No.{request_id}'
    

def view(id):
    reply = ''
    # Parameters for print formatting
    no_width = 3
    cate_width = 15
    desc_width = 20
    amt_width = 6

    reply += 'Here\'s your expense and income records:\n'
    reply += f'{"No.":{no_width}} {"Category":{cate_width}} {"Description":{desc_width}} {"Amount":{amt_width}}\n'
    reply += '=== =============== ==================== ======\n'
    
    rows = db.execute("SELECT * from records WHERE person_id = ?", id)

    for record in rows:
        reply += f'{record["record_id"]:<{no_width}} {record["category"]:{cate_width}} {record["description"]:{desc_width}} {record["amount"]:{amt_width}}\n'
        
    reply += '=== =============== ==================== ======\n'

    balance = 0
    # Sum up the amount of money of records
    for record in rows:
        balance += int(record["amount"])
    
    reply += f'Now you have {balance} dollars.'

    return reply


def add(id, record, num_of_rec):
    try:
        cate, desc, amt = record.split()
    except ValueError:
        # If the input string cannot be split into a list of two strings
        return 'The format of a record should be like this: meal breakfast -50.\nFail to add a record.'
    
    # Handle cate not in categories
    if not is_category_valid(cate):
        return 'The specified category is not in the category list.\n' \
        'You can check the category list by command "view categories".\n' \
        'Fail to add a record.'

    try:
        amt = int(amt) # Check if amt is a numberic string and convert it
    except ValueError:
        # If amt cannot be converted to integer
        return 'Invalid value for money.\nFail to add a record.'
    else:
        # Keep records a list of lists of strings for future str operations
        db.execute("INSERT INTO records (person_id, description, amount, record_id, category) VALUES(?, ?, ?, ?, ?)", id, desc, amt, num_of_rec+1, cate)
        # Update user's num_of_rec + 1
        update_num_of_rec(id, num_of_rec+1)

        return f'Successfully add a record No.{num_of_rec+1}: {cate} {desc} {amt}'


def delete(id, wanna_del, num_of_rec):
    try:
        wanna_del = int(wanna_del)
        assert 0 <= wanna_del <= num_of_rec # Ensure that the input is within the bounds
        
    except ValueError:
        # If the input cannot be converted into an integer
        return 'Invalid format. Fail to delete a record.'
        
    except AssertionError:
        # If the input is out of bounds
        return f'There\'s no record with No.{wanna_del}. Fail to delete a record.'
        
    else:
        if wanna_del == 0: # Do nothing if the input is 0
            return 'The deletion is skipped.'
        
        #wanna_del -= 1 # Need adjustment becuase No. is 1 based and the index is 0 based
        # Pop the record
        #deleted_desc, deleted_amt = records.pop(wanna_del)
        db.execute("DELETE FROM records WHERE person_id = ? AND record_id = ?", id, wanna_del)

        # Compactly update every record_id starting from deleted record_id
        for new_record_id in range(wanna_del, num_of_rec):
            old_record_id = new_record_id + 1
            db.execute("UPDATE records SET record_id = ? WHERE record_id = ?", new_record_id, old_record_id)
        
        # Update user's num_of_rec - 1
        update_num_of_rec(id, num_of_rec-1)

        return f'Successfully delete a record No.{wanna_del}'


def update_status(id, new_status):
    db.execute("UPDATE people SET status = ? WHERE id = ?", new_status, id)


def update_num_of_rec(id, new_num_of_rec):
    db.execute("UPDATE people SET num_of_rec = ? WHERE id = ?", new_num_of_rec, id)


def update_request_id(id, new_request_id):
    db.execute("UPDATE people SET request_id = ? WHERE id = ?", new_request_id, id)


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    reply = ''

    user_id = event.source.user_id
    rows = db.execute("SELECT * FROM people WHERE id = ?", user_id)
    if len(rows) == 0:
        db.execute("INSERT INTO people (id, status, num_of_rec) VALUES (?, ?, ?)", user_id, 'INIT', 0)
    
    rows = db.execute("SELECT * FROM people WHERE id = ?", user_id)
    user_status = rows[0]['status']
    user_num_of_rec = rows[0]['num_of_rec']

    if user_status == 'INIT':
        if text == 'add':
            reply = "Add an expense or income record with category, description, and amount: "
            update_status(user_id, 'ADD')

        elif text == 'view':
            reply = view(user_id)

        elif text == 'delete':
            reply = "Which record do you want to delete (0 to skip): No.?"
            update_status(user_id, 'DELETE')

        elif text == 'edit':
            reply = "Which record do you want to edit (0 to skip): No.?"
            update_status(user_id, 'EDIT_ASK_FOR_ID')

        elif text == 'view categories':
            reply = '\n'.join(view_categories())

        elif text == 'find':
            reply = "Which category do you want to find? "
            update_status(user_id, 'FIND')

        elif text == 'help':
            reply = ' / '.join(commands)

        else:
            reply = 'Invalid command. Try again.\nYou can check valid commands by "help".'
            #update_status(user_id, 'INIT')

    elif user_status == 'ADD':
        reply = add(user_id, text, user_num_of_rec)
        update_status(user_id, 'INIT')

    elif user_status == 'DELETE':
        reply = delete(user_id, text, user_num_of_rec)
        update_status(user_id, 'INIT')

    elif user_status == 'EDIT_ASK_FOR_ID':
        reply = edit_ask_for_id(user_id, text, user_num_of_rec)
        if reply == 'Edit the record with new category, description, and amount: ':
            update_status(user_id, 'EDIT')
        else:
            update_status(user_id, 'INIT')

    elif user_status == 'EDIT':
        reply = edit(user_id, text, user_num_of_rec)
        update_status(user_id, 'INIT')

    elif user_status == 'FIND':
        reply = find(user_id, text)
        update_status(user_id, 'INIT')

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )


if __name__ == "__main__":
    app.run()