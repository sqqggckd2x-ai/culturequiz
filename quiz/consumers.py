import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Question, Answer, Participant, Game, Round


class GameConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs'].get('game_id')
        self.group_name = f'game_{self.game_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # on new connection, if there is an active question and answers are accepted,
        # send the current question to the connecting client so page reloads see it
        @database_sync_to_async
        def _get_state(gid):
            try:
                g = Game.objects.select_related('active_question').get(pk=gid)
                started = None
                started_ts = None
                active_round_id = None
                active_round_started = None
                active_round_started_ts = None
                try:
                    if g.active_question_started_at:
                        started = g.active_question_started_at.isoformat()
                        started_ts = int(g.active_question_started_at.timestamp())
                except Exception:
                    started = None
                    started_ts = None
                try:
                    if g.active_round:
                        active_round_id = g.active_round_id
                        if g.active_round_started_at:
                            active_round_started = g.active_round_started_at.isoformat()
                            active_round_started_ts = int(g.active_round_started_at.timestamp())
                except Exception:
                    active_round_id = None
                return {
                    'accepting': g.accepting_answers,
                    'question_id': g.active_question_id,
                    'started_at': started,
                    'started_at_ts': started_ts,
                    'active_round_id': active_round_id,
                    'active_round_started': active_round_started,
                    'active_round_started_ts': active_round_started_ts,
                }
            except Exception:
                return {'accepting': False, 'question_id': None}

        state = await _get_state(int(self.game_id)) if self.game_id else {'accepting': False, 'question_id': None}
        if state.get('accepting') and state.get('question_id'):
            @database_sync_to_async
            def _load_question(qid):
                try:
                    q = Question.objects.get(pk=qid)
                    # Try to fetch started_at from the game's active_question_started_at if set
                    g = q.round.game
                    started = None
                    started_ts = None
                    try:
                        if g.active_question_started_at:
                            started = g.active_question_started_at.isoformat()
                            started_ts = int(g.active_question_started_at.timestamp())
                    except Exception:
                        started = None
                        started_ts = None
                    return {
                        'id': q.pk,
                        'text': q.text,
                        'type': q.type,
                        'options': q.options or [],
                        'time': getattr(q, 'time_limit', 30),
                        'allow_bet': bool(q.allow_bet),
                        'max_bet': getattr(q, 'max_bet', 10),
                        'started_at': started,
                        'started_at_ts': started_ts,
                    }
                except Exception:
                    return None

            qpayload = await _load_question(state.get('question_id'))
            if qpayload:
                await self.send_json({'type': 'show_question', 'question': qpayload})
        # If there's an active round, load and send it (including saved answers for this participant)
        if state.get('accepting') and state.get('active_round_id'):
            @database_sync_to_async
            def _load_round(rid, user_session):
                try:
                    r = Round.objects.get(pk=rid)
                    questions = []
                    for q in r.questions.all():
                        questions.append({
                            'id': q.pk,
                            'text': q.text,
                            'type': q.type,
                            'options': q.options or [],
                            'allow_bet': bool(q.allow_bet),
                            'points': q.points,
                        })
                    # load saved answers for this user in this round
                    saved = {}
                    if user_session:
                        ans_qs = Answer.objects.filter(user_id=user_session, question__round=r)
                        for a in ans_qs:
                            saved[a.question_id] = {'answer_text': a.answer_text, 'bet_used': a.bet_used}
                    started = None
                    started_ts = None
                    try:
                        g = r.game
                        if g.active_round_started_at:
                            started = g.active_round_started_at.isoformat()
                            started_ts = int(g.active_round_started_at.timestamp())
                    except Exception:
                        started = None
                        started_ts = None
                    return {'id': r.pk, 'title': r.title, 'questions': questions, 'saved_answers': saved, 'started_at': started, 'started_at_ts': started_ts}
                except Exception:
                    return None

            round_payload = await _load_round(state.get('active_round_id'), getattr(self, 'participant_id', None))
            if round_payload:
                await self.send_json({'type': 'show_round', 'round': round_payload})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')

        if action == 'join_game':
            # store participant id for this connection
            self.participant_id = content.get('participant_id')
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'player_joined',
                    'participant_id': self.participant_id,
                }
            )

        elif action == 'submit_answer':
            # legacy handling — treat as save
            question_id = content.get('question_id')
            answer_text = content.get('answer')
            bet = content.get('bet')
            participant_id = content.get('participant_id') or getattr(self, 'participant_id', None)
            saved_id = await self._save_or_update_answer(participant_id, question_id, answer_text, bet)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'player_submit',
                    'participant_id': participant_id,
                    'question_id': question_id,
                    'answer': answer_text,
                    'bet': bet,
                    'answer_id': saved_id,
                }
            )
        elif action == 'save_answer':
            question_id = content.get('question_id')
            answer_text = content.get('answer')
            bet = content.get('bet')
            participant_id = content.get('participant_id') or getattr(self, 'participant_id', None)
            saved_id = await self._save_or_update_answer(participant_id, question_id, answer_text, bet)
            # no broadcast needed for every save, but we can acknowledge via player_submit
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'player_submit',
                    'participant_id': participant_id,
                    'question_id': question_id,
                    'answer': answer_text,
                    'bet': bet,
                    'answer_id': saved_id,
                }
            )
        elif action == 'save_round_answers':
            # payload should contain list of {question_id, answer, bet}
            answers = content.get('answers') or []
            participant_id = content.get('participant_id') or getattr(self, 'participant_id', None)
            saved_ids = []
            for item in answers:
                qid = item.get('question_id')
                ans_text = item.get('answer')
                bet = item.get('bet')
                sid = await self._save_or_update_answer(participant_id, qid, ans_text, bet)
                if sid:
                    saved_ids.append(sid)
            # notify group that this participant saved (so admin can count)
            await self.channel_layer.group_send(self.group_name, {'type': 'player_submit', 'participant_id': participant_id, 'saved_ids': saved_ids})

    # Handlers for messages sent to the group by server/admin
    async def show_question(self, event):
        # event expected to contain 'question' and optional 'options'
        await self.send_json({
            'type': 'show_question',
            'question': event.get('question'),
            'options': event.get('options'),
        })

    async def stop_answers(self, event):
        await self.send_json({
            'type': 'stop_answers'
        })

    async def update_rating(self, event):
        await self.send_json({
            'type': 'update_rating',
            'ratings': event.get('ratings')
        })

    # simple forwarding handlers for player events
    async def player_submit(self, event):
        await self.send_json({
            'type': 'player_submit',
            'participant_id': event.get('participant_id'),
            'question_id': event.get('question_id'),
            'answer': event.get('answer'),
            'bet': event.get('bet'),
        })

    async def player_joined(self, event):
        await self.send_json({
            'type': 'player_joined',
            'participant_id': event.get('participant_id'),
        })

    @database_sync_to_async
    def _save_answer(self, participant_id, question_id, answer_text, bet):
        try:
            question = Question.objects.get(pk=question_id)
        except Question.DoesNotExist:
            return None

        participant = None
        if participant_id:
            participant = Participant.objects.filter(id=participant_id).first()

        user_id = participant.session_key if participant else 'anon'
        team_name = participant.team_name if participant else None

        # sanitize bet: only allow 1 or 2 as coefficients (0 means no bet)
        if question.allow_bet:
            try:
                bval = int(bet) if bet is not None else 0
            except Exception:
                bval = 0
            if bval not in (0, 1, 2):
                # clamp to 0 if unexpected
                bval = 0
            bet_stored = bval
        else:
            bet_stored = None

        ans = Answer.objects.create(
            question=question,
            user_id=user_id,
            team_name=team_name,
            answer_text=answer_text or '',
            bet_used=bet_stored,
        )
        return ans.id

    @database_sync_to_async
    def _save_or_update_answer(self, participant_id, question_id, answer_text, bet):
        try:
            question = Question.objects.get(pk=question_id)
        except Question.DoesNotExist:
            return None

        # ensure the game's accepting_answers flag is True
        g = question.round.game
        if not getattr(g, 'accepting_answers', False):
            return None

        participant = None
        if participant_id:
            participant = Participant.objects.filter(id=participant_id).first()

        user_id = participant.session_key if participant else 'anon'
        team_name = participant.team_name if participant else None

        # sanitize bet: only allow 1 or 2 (0 = no bet)
        if question.allow_bet:
            try:
                bval = int(bet) if bet is not None else 0
            except Exception:
                bval = 0
            if bval not in (0,1,2):
                bval = 0
            bet_stored = bval
        else:
            bet_stored = None

        # find existing answer for this user and question, update it; else create
        ans = Answer.objects.filter(question=question, user_id=user_id).first()
        if ans:
            ans.answer_text = answer_text or ''
            ans.bet_used = bet_stored
            ans.is_correct = None
            ans.points_awarded = None
            ans.save()
        else:
            ans = Answer.objects.create(
                question=question,
                user_id=user_id,
                team_name=team_name,
                answer_text=answer_text or '',
                bet_used=bet_stored,
            )
        return ans.id
