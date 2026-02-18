import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Question, Answer, Participant, Game


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
                return {'accepting': g.accepting_answers, 'question_id': g.active_question_id}
            except Exception:
                return {'accepting': False, 'question_id': None}

        state = await _get_state(int(self.game_id)) if self.game_id else {'accepting': False, 'question_id': None}
        if state.get('accepting') and state.get('question_id'):
            @database_sync_to_async
            def _load_question(qid):
                try:
                    q = Question.objects.get(pk=qid)
                    return {
                        'id': q.pk,
                        'text': q.text,
                        'type': q.type,
                        'options': q.options or [],
                        'time': getattr(q, 'time_limit', 30),
                        'allow_bet': bool(q.allow_bet),
                        'max_bet': getattr(q, 'max_bet', 10),
                    }
                except Exception:
                    return None

            qpayload = await _load_question(state.get('question_id'))
            if qpayload:
                await self.send_json({'type': 'show_question', 'question': qpayload})

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
            # payload should contain 'question_id', 'answer', and optional 'bet'
            question_id = content.get('question_id')
            answer_text = content.get('answer')
            bet = content.get('bet')
            participant_id = content.get('participant_id') or getattr(self, 'participant_id', None)

            # persist answer to DB
            saved_id = await self._save_answer(participant_id, question_id, answer_text, bet)

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

        ans = Answer.objects.create(
            question=question,
            user_id=user_id,
            team_name=team_name,
            answer_text=answer_text or '',
            bet_used=bet if bet is not None else None,
        )
        return ans.id
