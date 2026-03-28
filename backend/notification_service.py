try:
    from app.plugins.slack_client import SlackClient
except ImportError:
    from app.plugins.slack_client import SlackClient

slack_client = SlackClient()

def _format_user(user_dict: dict) -> str:
    return f"{user_dict.get('displayName', user_dict.get('username'))} ({user_dict.get('email')})"

def notify_user_registered(background_tasks, user_dict: dict):
    """Notify Slack when a new user registers."""
    message = f":tada: New user registered: {_format_user(user_dict)}"
    background_tasks.add_task(slack_client.send_message, message)

def notify_task_created(background_tasks, task: dict, actor: dict):
    """Notify Slack when a task is created."""
    message = (
        f":memo: Task *{task.get('title')}* created by {_format_user(actor)}. "
        f"Assignee: {task.get('assignee')}."
    )
    background_tasks.add_task(slack_client.send_message, message)

def notify_task_updated(background_tasks, task: dict, actor: dict):
    """Notify Slack when a task is updated."""
    message = (
        f":pencil2: Task *{task.get('title')}* updated by {_format_user(actor)}. "
        f"Status: {task.get('status')}"
    )
    background_tasks.add_task(slack_client.send_message, message)

def notify_task_commented(background_tasks, task_id: int, comment: dict, actor: dict):
    """Notify Slack when a comment is added to a task."""
    message = (
        f":speech_balloon: New comment on task #{task_id} by {_format_user(actor)}: \"{comment.get('comment')}\""
    )
    background_tasks.add_task(slack_client.send_message, message)
