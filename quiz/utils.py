from django.db.models import Sum
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def update_score(participant, question, answer, bet_used):
    """
    Calculate points for an answer and update participant.total_score.

    Logic:
    - If bet_used is truthy (>0):
        - If answer.is_correct is True: points_awarded = question.points * bet_used * question.bet_multiplier
        - If answer.is_correct is False: points_awarded = - (question.points * bet_used * question.bet_multiplier)
    - If no bet_used or bet_used == 0:
        - If answer.is_correct is True: points_awarded = question.points
        - Else: points_awarded = 0

    After setting answer.points_awarded and saving it, recalculate participant.total_score
    as the sum of all awarded points for that participant in the game, persist it and
    broadcast updated ratings to the WebSocket group `game_<game_id>`.
    """
    # defensive defaults
    try:
        bet = int(bet_used) if bet_used is not None else 0
    except Exception:
        bet = 0

    if answer.is_correct:
        if bet > 0:
            pts = question.points * bet * question.bet_multiplier
        else:
            pts = question.points
    else:
        if bet > 0:
            pts = - (question.points * bet * question.bet_multiplier)
        else:
            pts = 0

    answer.points_awarded = pts
    answer.save()

    # Recalculate participant total for this game
    game = question.round.game
    if participant is None:
        # nothing to update
        return

    total = answer.__class__.objects.filter(user_id=participant.session_key, question__round__game=game, points_awarded__isnull=False).aggregate(total=Sum('points_awarded'))['total'] or 0
    participant.total_score = total
    participant.save()

    # Broadcast updated ratings
    participants = list(game.participants.all())
    ratings = []
    for p in participants:
        ratings.append({'participant_id': p.id, 'session_key': p.session_key, 'team_name': p.team_name, 'score': p.total_score})

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f'game_{game.id}', {'type': 'update_rating', 'ratings': ratings})
