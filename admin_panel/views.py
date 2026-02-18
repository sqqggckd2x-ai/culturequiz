from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db import models

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from quiz.models import Game, Question, Answer, Participant


def superuser_required(user):
    return user.is_active and user.is_superuser


@login_required
@user_passes_test(superuser_required)
def manage_game(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    rounds = game.rounds.all().prefetch_related('questions')

    # ratings per participant (session_key)
    participants = list(game.participants.all())
    ratings = []
    for p in participants:
        total = Answer.objects.filter(user_id=p.session_key, question__round__game=game, points_awarded__isnull=False).aggregate(total=models.Sum('points_awarded'))['total'] or 0
        ratings.append({'participant': p, 'score': total})

    return render(request, 'admin_panel/manage_game.html', {
        'game': game,
        'rounds': rounds,
        'ratings': sorted(ratings, key=lambda r: r['score'], reverse=True),
    })


@login_required
@user_passes_test(superuser_required)
@require_POST
def send_question(request, game_id, question_id):
    question = get_object_or_404(Question, pk=question_id, round__game__id=game_id)
    duration = int(request.POST.get('duration', 30))

    payload = {
        'type': 'show_question',
        'question': {
            'id': question.id,
            'text': question.text,
            'type': question.type,
            'options': question.options or [],
            'allow_bet': question.allow_bet,
            'max_bet': 10,
        },
        'time': duration,
    }

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f'game_{game_id}', payload)

    # persist active question state on game so reconnecting clients can read it
    game = Game.objects.get(pk=game_id)
    game.active_question = question
    game.accepting_answers = True
    game.save()

    return redirect(reverse('admin_panel:manage_game', args=[game_id]))


@login_required
@user_passes_test(superuser_required)
@require_POST
def stop_answers(request, game_id):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f'game_{game_id}', {'type': 'stop_answers'})
    # persist state
    game = Game.objects.get(pk=game_id)
    game.accepting_answers = False
    game.save()
    return redirect(reverse('admin_panel:manage_game', args=[game_id]))


@login_required
@user_passes_test(superuser_required)
@require_POST
def stop_answers_question(request, game_id, question_id):
    # stop accepting answers (immediately) for current active question
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f'game_{game_id}', {'type': 'stop_answers', 'question_id': question_id})
    # persist state on game
    game = Game.objects.get(pk=game_id)
    game.accepting_answers = False
    # if active_question matches, clear it
    if game.active_question and game.active_question.id == question_id:
        game.active_question = None
    game.save()
    return redirect(reverse('admin_panel:manage_game', args=[game_id]))


@login_required
@user_passes_test(superuser_required)
def moderate_answers(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    # open type questions' answers which are not yet moderated
    answers = Answer.objects.filter(question__round__game=game, question__type=Question.TYPE_OPEN, is_correct__isnull=True).select_related('question')
    return render(request, 'admin_panel/moderate_answers.html', {'game': game, 'answers': answers})


@login_required
@user_passes_test(superuser_required)
@require_POST
def mark_answer(request, game_id, answer_id):
    action = request.POST.get('action')
    ans = get_object_or_404(Answer, pk=answer_id, question__round__game__id=game_id)
    is_correct = True if action == 'correct' else False
    ans.is_correct = is_correct

    # calculate points_awarded
    q = ans.question
    bet = ans.bet_used or 0
    if bet:
        # if bet placed: points = question.points * (bet * bet_multiplier)
        delta = q.points * (bet * q.bet_multiplier)
        ans.points_awarded = delta if is_correct else -delta
    else:
        ans.points_awarded = q.points if is_correct else 0

    ans.save()

    # notify group to update ratings
    # build ratings after change
    channel_layer = get_channel_layer()
    # simple trigger: send update_rating with recalculated ratings
    participants = list(Game.objects.get(pk=game_id).participants.all())
    ratings = []
    for p in participants:
        total = Answer.objects.filter(user_id=p.session_key, question__round__game_id=game_id, points_awarded__isnull=False).aggregate(total=models.Sum('points_awarded'))['total'] or 0
        ratings.append({'participant_id': p.id, 'session_key': p.session_key, 'team_name': p.team_name, 'score': total})

    async_to_sync(channel_layer.group_send)(f'game_{game_id}', {'type': 'update_rating', 'ratings': ratings})

    # redirect back to caller if provided
    next_url = request.POST.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)

    return redirect(reverse('admin_panel:moderate_answers', args=[game_id]))


@login_required
@user_passes_test(superuser_required)
def moderate_answers_question(request, game_id, question_id):
    game = get_object_or_404(Game, pk=game_id)
    question = get_object_or_404(Question, pk=question_id, round__game=game)
    # show answers for this question (unmoderated first)
    answers = Answer.objects.filter(question=question).select_related('question')
    return render(request, 'admin_panel/moderate_answers_question.html', {'game': game, 'question': question, 'answers': answers})
