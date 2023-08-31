#!/usr/bin/env python3
# Author: Shane Harrell
# Email: shane.harrell@signalwire.com
# Purpose: Working example of an AI bot that will ask questions to a user, and store the answers in a database.

import json
from flask import Flask, redirect, render_template, request, url_for
import sqlite3


surveybot = Flask(__name__)

@surveybot.route('/', methods=['POST'])
def main_ai_prompt():
    swml_web_hook_base_url = '<your_webhook_url>'
    swml_ai_prompt = '''Your name is SurveyBot.  Your job is to survey the caller with questions from a database.
    
    ### How to follow up on questions answered and protocols to follow                   
        Stay on focus and on protocol.
        You are not capable of troubleshooting or diagnosing problems.
        Execute functions when appropriate
    
    ### Step 1
        Determine if the caller already exists in the database.  Use the provided lookup_caller function using the callers phone number as an argument.
        
    ### Step 2
        We need to gather some data about the caller so that we can record their answers.
        
    #### Step 2.1
        Ask the caller for their first name
    
    #### Step 2.2
        Ask the caller for their last name
    
    #### Step 2.3
        Ask the caller for their age in years
        
    #### Step 2.4
        Use the calling phone number as the callers phone number.  Use the provided create_user function to create the user in the database.
        Do not tell the caller that a record was created in a database.
    
    ### Step 3
        Ask the caller the first question when it is returned.
        Continue to use the provided question_and_answer function to record each answer, and get the next question.  Send the question asked in the question argument, and the answer in the answer argument.
        Stay on task and on protocol. Do not make up your own questions. 
        Repeat this process until there are no questions remaining.
    '''

    swml = {}
    swml['sections'] = {
        'main': [{
            'ai': {
                'voice': 'en-US-Standard-A',
                'params': {
                    'confidence': 0.6,
                    'barge_confidence': 0.1,
                    'top_p': 0.3,
                    'temperature': 1.0,
                    'swaig_allow_swml': True,
                    'conscience': True
                },
                'prompt': {
                    'text': swml_ai_prompt
                },
                'SWAIG': {
                    'functions': [
                        {
                            'function': 'lookup_caller',
                            'purpose': 'lookup the caller in the database to see if they exist',
                            'web_hook_url': f"{swml_web_hook_base_url}/lookup_caller",
                            'argument': {
                                'type': 'object',
                                'properties': {
                                    'phone_number': {
                                        'type': 'string',
                                        'description': 'the callers phone_number'
                                    }
                                }
                            }
                        },
                        {
                            'function': 'question_and_answer',
                            'purpose': 'record the answer and get the next question for the survey',
                            'web_hook_url': f"{swml_web_hook_base_url}/question_and_answer",
                            'argument': {
                                'type': 'object',
                                'properties': {
                                    'answer': {
                                        'type': 'string',
                                        'description': 'the callers answer to the question'
                                    },
                                    'question': {
                                        'type': 'string',
                                        'description': 'the question that was asked by SurveyBot'
                                    }
                                }
                            }
                        },
                        {
                            'function': 'create_user_record',
                            'purpose': 'submit the payment for the caller',
                            'web_hook_url': f"{swml_web_hook_base_url}/create_user",
                            'argument': {
                                'type': 'object',
                                'properties': {
                                    'first_name': {
                                        'type': 'string',
                                        'description': 'the callers fist name'
                                    },
                                    'last_name': {
                                        'type': 'string',
                                        'description': 'the callers last name'
                                    },
                                    'age': {
                                        'type': 'string',
                                        'description': 'the callers age'
                                    },
                                    'phone_number': {
                                        'type': 'string',
                                        'description': 'the callers phone_number'
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }]
    }

    return (swml)

# SWAIG FUNCTION ENDPOINTS
@surveybot.route('/lookup_caller', methods=['POST'])
def lookup_caller():
    db = sqlite3.connect("survey.db")
    cursor = db.cursor()

    swml = {}

    # Does this user already exist in the database
    # Don't create a new user if they do
    phone_number = request.json['argument']['parsed'][0]['phone_number']

    rows = cursor.execute(
        "SELECT id, first_name, last_name from user where phone_number = ? limit 1",
        (phone_number,)
    ).fetchall()

    if len(rows) > 0:
        for row in rows:
            global user_id
            user_id = row[0]
            first_name = row[1]
            last_name = row[2]

            add_questions_to_user(user_id)       # Add any new questions to the caller's survey
            question = get_a_question(user_id)   # Get the first/next question for the caller

            if question != "0":
                swml['response'] = f"The user already exists.  They callers name is {first_name} {last_name}.  The the first question is {question}"
                print (f"SWML: {swml}")
            else:
                swml['response'] = f"The user, {first_name} {last_name} already exists and they have already answered all of the questions in the survey.  Let the caller know they have already answered all of the questions and disconnect the call."
    else:
        swml['response'] = "The user does not exist, start with Step 2"

    db.close()
    print (f"{swml}")
    return swml

@surveybot.route('/create_user', methods=['POST'])
def create_user_record():
    db = sqlite3.connect("survey.db")
    cursor = db.cursor()

    swml = {}

    first_name = request.json['argument']['parsed'][0]['first_name']
    last_name = request.json['argument']['parsed'][0]['last_name']
    age = request.json['argument']['parsed'][0]['age']
    phone_number = request.json['argument']['parsed'][0]['phone_number']

    cursor.execute(
        "INSERT INTO user (first_name, last_name, age, phone_number) VALUES (?, ?, ?, ?)",
        (first_name, last_name, age, phone_number,)
    )
    db.commit()

    # Lets sneakily add the user_id as a global var for later inserts, so we don't have to look it up each time
    rows = cursor.execute(
        "SELECT id from user where phone_number = ? limit 1",
        (phone_number,)
    ).fetchall()
    for row in rows:
        global user_id
        user_id = row[0]

    add_questions_to_user(user_id)
    question = get_a_question(user_id)

    if question != "0":
        swml['response'] = f"The first question is {question}"
        print (f"SWML: {swml}")
    else:
        swml['response'] = f"There are no questions left.  Thank the caller and disconnect"
        print (f"SWML: {swml}")

    db.close()
    return swml

@surveybot.route('/question_and_answer', methods=['POST'])
def question_and_answer():
    swml = {}
    global question_id

    # UNCOMMENT FOR DEBUG:
    #print (request.json)

    db = sqlite3.connect("survey.db")
    cursor = db.cursor()

    answer = request.json['argument']['parsed'][0]['answer']

    cursor.execute(
        "UPDATE poll_answers SET answer = ? WHERE user_id = ? AND id = ?",
        (answer, user_id, question_id)
    )
    db.commit()

    rows = cursor.execute(
        "SELECT question, id from poll_answers where user_id = ? and answer is NULL order by id limit 1",
        (user_id,)
    ).fetchall()

    if len(rows) > 0:
        for row in rows:
            question = row[0]
            question_id = row[1]
            swml['response'] = f"Success.  The answer has been recorded.  the next question is {question}"
            print(f"{swml}")
    else:
        swml['response'] = f"Success.  The answer has been recorded.  There are no more questions in the survey.  Please hang up the call"
        print (f"{swml}")

    db.close()
    return swml


def get_a_question(user_id):
    global question_id
    response = ""

    db = sqlite3.connect("survey.db")
    cursor = db.cursor()

    rows = cursor.execute(
        "SELECT question, id from poll_answers where user_id = ? and answer is NULL order by id limit 1",
        (user_id,)
    ).fetchall()

    if len(rows) > 0:
        for row in rows:
            question = row[0]
            question_id = row[1]
            response = question
    else:
        response = "0"

    db.close()
    return (response)


def add_questions_to_user(user_id):
    db = sqlite3.connect("survey.db")
    cursor = db.cursor()

    rows = cursor.execute(
        "select id, question from poll_questions"
    ).fetchall()
    for row in rows:
        poll_question_id = row[0]
        poll_question = row[1]
        cursor.execute(
            "INSERT INTO poll_answers (user_id, question_id, question) SELECT ?, ?, ? WHERE NOT EXISTS (SELECT id from poll_answers where user_id = ? and question_id = ?)",
            (user_id, poll_question_id, poll_question, user_id, poll_question_id,)
        )

    db.commit()
    db.close()
    return



if __name__ == '__main__':
    surveybot.run(port='80')
