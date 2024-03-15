from myapp import create_app
from myapp.database import db, Message, ChatMessage
from flask_socketio import emit, join_room, leave_room

app, socket = create_app()


# COMMUNICATION ARCHITECTURE

# Join-chat event. Emit online message to other users and join the room
@socket.on("join-chat")
def join_private_chat(data):
    room = data["rid"]
    join_room(room=room)
    socket.emit(
        "joined-chat",
        {"msg": f"{room} is now online."},
        room=room,
        # include_self=False,
    )


# Outgoing event handler
@socket.on("outgoing")
def chatting_event(json, methods=["GET", "POST"]):
    """
    Handles saving messages and sending messages to all clients.
    :param json: JSON object containing message information.
    :param methods: List of HTTP methods allowed for this route.
    :return: None
    """
    room_id = json.get("rid")
    timestamp = json.get("timestamp")
    message_content = json.get("message")
    sender_id = json.get("sender_id")
    sender_username = json.get("sender_username")

    if not room_id or not timestamp or not message_content or not sender_id or not sender_username:
        # If any required field is missing, log the error and return early
        print("Error: Missing required fields in message JSON.")
        return

    try:
        # Get the message entry for the chat room
        message_entry = Message.query.filter_by(room_id=room_id).first()

        if not message_entry:
            # If no message entry exists, create a new one
            message_entry = Message(room_id=room_id)
            db.session.add(message_entry)
            db.session.commit()

        # Add the new message to the conversation
        chat_message = ChatMessage(
            content=message_content,
            timestamp=timestamp,
            sender_id=sender_id,
            sender_username=sender_username,
            room_id=room_id,
        )

        # Add the new chat message to the messages relationship of the message
        message_entry.messages.append(chat_message)

        # Update the database with the new message
        db.session.add(chat_message)
        db.session.commit()

        # Emit the message(s) sent to other users in the room
        socket.emit(
            "message",
            json,
            room=room_id,
            include_self=False,
        )
    except Exception as e:
        # Handle the database error or any other unexpected error
        print(f"Error processing message: {str(e)}")
        db.session.rollback()


if __name__ == "__main__":
    socket.run(app, allow_unsafe_werkzeug=True, debug=True)
