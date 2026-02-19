from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db import transaction
from . import models
from django import forms
import json
import logging
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'is_active', 'mode', 'created_at', 'manage_link')
    search_fields = ('title', 'description')
    actions = ('activate_selected_games', 'duplicate_games')

    def manage_link(self, obj):
        try:
            url = reverse('admin_panel:manage_game', args=[obj.id])
        except Exception:
            url = f'/admin/game/{obj.id}/manage/'
        return mark_safe(f'<a class="button" href="{url}">Перейти в панель управления</a>')

    manage_link.short_description = 'Панель'

    @admin.action(description='Активировать выбранные игры и деактивировать остальные')
    def activate_selected_games(self, request, queryset):
        selected_ids = list(queryset.values_list('id', flat=True))
        models.Game.objects.exclude(id__in=selected_ids).update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, f'Активировано {queryset.count()} игра(ы), остальные деактивированы.')

    @admin.action(description='Дублировать выбранные игры (с раундами и вопросами)')
    def duplicate_games(self, request, queryset):
        created = 0
        with transaction.atomic():
            for game in queryset:
                new_game = models.Game.objects.create(
                    title=f"{game.title} (копия)",
                    description=game.description,
                    is_active=False,
                    mode=game.mode,
                )
                for rnd in game.rounds.all().order_by('order'):
                    new_round = models.Round.objects.create(
                        game=new_game,
                        title=rnd.title,
                        order=rnd.order,
                        description=rnd.description,
                    )
                    for q in rnd.questions.all():
                        models.Question.objects.create(
                            round=new_round,
                            text=q.text,
                            type=q.type,
                            options=q.options,
                            correct_answer=q.correct_answer,
                            points=q.points,
                            allow_bet=q.allow_bet,
                            bet_multiplier=q.bet_multiplier,
                        )
                created += 1
        self.message_user(request, f'Создано копий: {created}.')


@admin.register(models.Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'game', 'order')
    search_fields = ('title', 'description', 'game__title')


@admin.register(models.Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'round', 'type', 'points', 'allow_bet')
    list_display_links = ('text',)
    search_fields = ('text',)
    list_display_links = ('text',)
    list_display = ('id', 'text', 'round', 'type', 'points', 'allow_bet', 'manage_controls')
    list_display_links = ('text',)
    search_fields = ('text',)

    inlines = []

    class AnswerInline(admin.TabularInline):
        model = models.Answer
        fields = ('user_id', 'team_name', 'answer_text', 'is_correct', 'points_awarded', 'submitted_at')
        readonly_fields = ('user_id', 'team_name', 'answer_text', 'submitted_at')
        extra = 0

    inlines = [AnswerInline]

    class QuestionForm(forms.ModelForm):
        options_text = forms.CharField(
            label='Варианты (по строке)', required=False,
            widget=forms.Textarea(attrs={'rows':4}),
            help_text='Если тип = "выбор", укажите один вариант на строку. Для открытого типа оставьте пустым.'
        )

        class Meta:
            model = models.Question
            fields = '__all__'

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # populate options_text from JSON list
            opts = None
            try:
                opts = self.instance.options
            except Exception:
                opts = None
            if opts:
                if isinstance(opts, (list, tuple)):
                    self.initial['options_text'] = '\n'.join(str(x) for x in opts)
                else:
                    # fallback to raw representation
                    self.initial['options_text'] = str(opts)

        def clean(self):
            cleaned = super().clean()
            qtype = cleaned.get('type')
            opts_text = cleaned.get('options_text', '')
            if qtype == models.Question.TYPE_CHOICE:
                # require at least one option
                opts = [line.strip() for line in opts_text.splitlines() if line.strip()]
                # If user supplied comma-separated values on a single line, split them too
                if len(opts) == 1 and ',' in opts[0]:
                    parts = [p.strip() for p in opts[0].split(',') if p.strip()]
                    if parts:
                        opts = parts
                if not opts:
                    raise forms.ValidationError('Для типа "выбор" нужно указать хотя бы один вариант.')
                cleaned['options'] = opts
            else:
                cleaned['options'] = None
            return cleaned

        def save(self, commit=True):
            # Ensure options JSON is stored on the instance even if 'options' isn't a displayed form field
            instance = super().save(commit=False)
            opts = self.cleaned_data.get('options', None)
            instance.options = opts
            if commit:
                instance.save()
            return instance

    form = QuestionForm
    fields = ('round', 'text', 'type', 'options_text', 'correct_answer', 'points', 'allow_bet', 'bet_multiplier')

    def save_model(self, request, obj, form, change):
        # Ensure options JSON is stored on the model even when 'options' isn't
        # included in the admin 'fields' list. Use cleaned_data from the form.
        opts = None
        try:
            opts = form.cleaned_data.get('options', None)
        except Exception:
            opts = None
        # Normalize string payloads into a list when necessary (robust against
        # values like "a, b, c" or raw JSON strings). If opts is already a
        # list or None, keep as-is.
        if isinstance(opts, str):
            normalized = None
            # Try parse JSON first (e.g. '[]' or '"foo"')
            try:
                parsed = json.loads(opts)
                if isinstance(parsed, (list, tuple)):
                    normalized = list(parsed)
                elif parsed is None:
                    normalized = None
                else:
                    # Single value -> single-item list
                    normalized = [str(parsed)]
            except Exception:
                # Fallback: split on newlines or commas
                lines = [p.strip() for p in opts.splitlines() if p.strip()]
                if not lines:
                    # try comma-separated
                    parts = [p.strip() for p in opts.split(',') if p.strip()]
                    normalized = parts or None
                else:
                    normalized = lines
            opts = normalized
        if opts is not None:
            obj.options = opts
        # Log for debugging — will appear in container stdout
        # Print unconditionally so output appears in container logs regardless
        # of logging configuration.
        try:
            print('QuestionAdmin.save_model: obj=%s form.cleaned_data=%r' % (getattr(obj, 'pk', None), getattr(form, 'cleaned_data', None)))
            print('QuestionAdmin.save_model: normalized opts=%r' % (opts,))
        except Exception:
            pass
        super().save_model(request, obj, form, change)

    # ---- Admin URLs for send / stop actions ----
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/send/', self.admin_site.admin_view(self.send_to_players), name='quiz_question_send'),
            path('<int:pk>/stop/', self.admin_site.admin_view(self.stop_answers_view), name='quiz_question_stop'),
        ]
        return custom_urls + urls

    def manage_controls(self, obj):
        send_url = f'./{obj.pk}/send/'
        stop_url = f'./{obj.pk}/stop/'
        moderate_url = f'/admin/quiz/answer/?question__id__exact={obj.pk}'
        return format_html(
            '<a class="button" href="{}">Отправить игрокам</a>&nbsp;'
            '<a class="button" href="{}">Остановить приём</a>&nbsp;'
            '<a class="button" href="{}">Модерировать ответы</a>',
            send_url, stop_url, moderate_url
        )
    manage_controls.short_description = 'Управление'

    def send_to_players(self, request, pk):
        q = models.Question.objects.filter(pk=pk).select_related('round__game').first()
        if not q:
            self.message_user(request, 'Вопрос не найден', level='error')
            return redirect(request.META.get('HTTP_REFERER', '..'))

        game = q.round.game
        # mark game state: active question and start time
        game.active_question = q
        game.accepting_answers = True
        game.active_question_started_at = timezone.now()
        game.save()

        # build question payload including server start timestamp for sync
        question_payload = {
            'id': q.pk,
            'text': q.text,
            'type': q.type,
            'options': q.options or [],
            'time': getattr(q, 'time_limit', 30),
            'allow_bet': bool(q.allow_bet),
            'max_bet': getattr(q, 'max_bet', 10),
            'started_at': game.active_question_started_at.isoformat(),
        }
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'game_{game.id}',
            {
                'type': 'show_question',
                'question': question_payload,
            }
        )
        self.message_user(request, f'Вопрос #{q.pk} отправлен игрокам')
        return redirect(request.META.get('HTTP_REFERER', '..'))

    def stop_answers_view(self, request, pk):
        q = models.Question.objects.filter(pk=pk).select_related('round__game').first()
        if not q:
            self.message_user(request, 'Вопрос не найден', level='error')
            return redirect(request.META.get('HTTP_REFERER', '..'))
        game = q.round.game
        # clear accepting and start time
        game.accepting_answers = False
        game.active_question_started_at = None
        game.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'game_{game.id}',
            {
                'type': 'stop_answers',
            }
        )
        self.message_user(request, f'Приём ответов для вопроса #{q.pk} остановлен')
        return redirect(request.META.get('HTTP_REFERER', '..'))


@admin.register(models.Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'user_id', 'team_name', 'is_correct', 'points_awarded', 'submitted_at')
    search_fields = ('user_id', 'team_name', 'answer_text')


@admin.register(models.Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_key', 'game', 'team_name', 'registered_at')
    search_fields = ('session_key', 'team_name')
