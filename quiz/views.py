from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest
from .models import Game
from django.http import JsonResponse
from .models import Participant

import qrcode
from io import BytesIO
import base64
from django.shortcuts import redirect
from django.urls import reverse
from .models import Participant
import uuid


def game_stream(request: HttpRequest, game_id: int):
    game = get_object_or_404(Game, pk=game_id)

    # Registration URL (relative as requested)
    registration_path = f'/game/{game_id}/register/'

    # Prefer absolute URL for QR so scanners work across devices
    registration_url = request.build_absolute_uri(registration_path)

    # Generate QR code image and encode as base64 PNG
    qr_img = qrcode.make(registration_url)
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')

    context = {
        'game': game,
        'qr_base64': qr_b64,
        'registration_path': registration_path,
    }

    return render(request, 'quiz/stream.html', context)


def register_for_game(request: HttpRequest, game_id: int):
    game = get_object_or_404(Game, pk=game_id)

    # Ensure session exists
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key

    if request.method == 'POST':
        if game.mode == Game.MODE_TEAM:
            team_name = request.POST.get('team_name', '').strip()
            if not team_name:
                return render(request, 'quiz/register.html', {'game': game, 'error': 'Team name is required for team games.'})
            participant = Participant.objects.create(session_key=session_key, game=game, team_name=team_name)
        else:
            player_name = request.POST.get('player_name', '').strip()
            if not player_name:
                # generate a short name
                player_name = f'Player-{uuid.uuid4().hex[:8]}'
            participant = Participant.objects.create(session_key=session_key, game=game, team_name=player_name)

        # store participant id in session for convenience
        request.session['participant_id'] = participant.id

        return redirect(f'/game/{game_id}/play/')

    # GET
    return render(request, 'quiz/register.html', {'game': game})


def play_game(request: HttpRequest, game_id: int):
    game = get_object_or_404(Game, pk=game_id)

    # Ensure session exists and participant id if any
    if not request.session.session_key:
        request.session.save()

    ws_scheme = 'wss' if request.is_secure() else 'ws'
    host = request.get_host()
    ws_url = f"{ws_scheme}://{host}/ws/game/{game_id}/"

    participant_id = request.session.get('participant_id')

    return render(request, 'quiz/play.html', {'game': game, 'ws_url': ws_url, 'participant_id': participant_id})


def ratings(request, game_id: int):
    game = get_object_or_404(Game, pk=game_id)
    participants = game.participants.all()
    data = []
    for p in participants:
        data.append({'participant_id': p.id, 'session_key': p.session_key, 'team_name': p.team_name, 'score': p.total_score})
    # sort desc
    data = sorted(data, key=lambda x: x['score'], reverse=True)
    return JsonResponse({'ratings': data})


def index(request: HttpRequest):
    """Redirect root to latest active game's stream or to admin if none."""
    latest = Game.objects.filter(is_active=True).order_by('-created_at').first()
    if latest:
        return redirect('quiz:game_stream', game_id=latest.id)
    return redirect('/admin/')
