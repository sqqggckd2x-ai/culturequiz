from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


class Game(models.Model):
    MODE_TEAM = 'team'
    MODE_INDIVIDUAL = 'individual'
    MODE_CHOICES = [
        (MODE_TEAM, 'команда'),
        (MODE_INDIVIDUAL, 'индивидуально'),
    ]

    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    video_url = models.CharField('Видео (embed URL)', max_length=500, blank=True, null=True, help_text='VK video embed URL')
    created_at = models.DateTimeField('Дата создания', default=timezone.now)
    is_active = models.BooleanField('Активна', default=True)
    # currently active question and whether accepting answers
    active_question = models.ForeignKey('Question', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    # currently active round (for round-level sending)
    active_round = models.ForeignKey('Round', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    accepting_answers = models.BooleanField('Принимаются ответы', default=False)
    active_question_started_at = models.DateTimeField('Время старта активного вопроса', null=True, blank=True)
    active_round_started_at = models.DateTimeField('Время старта активного раунда', null=True, blank=True)
    mode = models.CharField('Режим', max_length=20, choices=MODE_CHOICES, default=MODE_INDIVIDUAL)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Игра'
        verbose_name_plural = 'Игры'


class Round(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='rounds', verbose_name='Игра')
    title = models.CharField('Название раунда', max_length=255)
    order = models.PositiveIntegerField('Порядок')
    description = models.TextField('Описание раунда', blank=True, null=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Раунд'
        verbose_name_plural = 'Раунды'

    def __str__(self):
        return f"{self.game.title} — {self.title}"


class Question(models.Model):
    TYPE_CHOICE = 'choice'
    TYPE_OPEN = 'open'
    TYPE_CHOICES = [
        (TYPE_CHOICE, 'выбор'),
        (TYPE_OPEN, 'открытый'),
    ]

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='questions', verbose_name='Раунд')
    text = models.TextField('Текст вопроса')
    type = models.CharField('Тип', max_length=10, choices=TYPE_CHOICES, default=TYPE_CHOICE)
    options = models.JSONField('Варианты (JSON)', blank=True, null=True, help_text='Store list of option strings')
    correct_answer = models.TextField('Правильный ответ', blank=True, null=True, help_text='For choice must match one option; for open — moderator reference')
    points = models.PositiveIntegerField('Очки', validators=[MinValueValidator(1)])
    allow_bet = models.BooleanField('Разрешена ставка', default=False)
    bet_multiplier = models.PositiveIntegerField('Множитель ставки', default=1)

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'

    def __str__(self):
        return f"Q#{self.pk}: {self.text[:50]}"


class Participant(models.Model):
    session_key = models.CharField('Ключ сессии', max_length=255)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='participants', verbose_name='Игра')
    team_name = models.CharField('Название команды / имя', max_length=255, blank=True, null=True)
    last_name = models.CharField('Фамилия', max_length=150, blank=True, null=True)
    first_name = models.CharField('Имя', max_length=150, blank=True, null=True)
    middle_name = models.CharField('Отчество', max_length=150, blank=True, null=True)
    registered_at = models.DateTimeField('Время регистрации', default=timezone.now)
    total_score = models.IntegerField('Всего очков', default=0)

    class Meta:
        verbose_name = 'Участник'
        verbose_name_plural = 'Участники'
        ordering = ['-total_score']

    def __str__(self):
        if self.team_name:
            return f"{self.team_name} ({self.game.title})"
        # fallback to composed name if available
        parts = [p for p in [self.last_name, self.first_name, self.middle_name] if p]
        if parts:
            return f"{' '.join(parts)} ({self.game.title})"
        return f"{self.session_key} ({self.game.title})"

    @property
    def full_name(self):
        parts = [p for p in [self.last_name, self.first_name, self.middle_name] if p]
        return ' '.join(parts) if parts else (self.team_name or '')


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers', verbose_name='Вопрос')
    user_id = models.CharField('ID пользователя (сессия)', max_length=255)
    team_name = models.CharField('Название команды / имя', max_length=255, blank=True, null=True)
    answer_text = models.TextField('Текст ответа')
    is_correct = models.BooleanField('Правильный', null=True)
    points_awarded = models.IntegerField('Начисленные очки', blank=True, null=True)
    bet_used = models.PositiveIntegerField('Ставка', blank=True, null=True)
    submitted_at = models.DateTimeField('Время отправки', auto_now_add=True)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'

    def __str__(self):
        return f"Ответ {self.user_id} на Q#{self.question_id}"

    def save(self, *args, **kwargs):
        # Auto-evaluate choice answers when question.correct_answer exists
        try:
            q = self.question
        except Exception:
            q = None

        if getattr(q, 'type', None) == Question.TYPE_CHOICE and getattr(q, 'correct_answer', None):
            # Only auto-set is_correct when it's not explicitly set (allow moderator override later)
            if self.is_correct is None:
                try:
                    # simple normalization: strip + lower
                    if (self.answer_text or '').strip().lower() == (q.correct_answer or '').strip().lower():
                        self.is_correct = True
                    else:
                        self.is_correct = False
                except Exception:
                    # fall back to leaving is_correct as-is
                    pass

        # If is_correct is set and points_awarded not calculated yet, defer to util to compute
        is_set = self.is_correct is not None
        need_calc = self.points_awarded is None
        super().save(*args, **kwargs)
        if is_set and need_calc:
            # avoid circular import at module load
            from .utils import update_score
            # try to find participant for this answer
            participant = None
            try:
                participant = Participant.objects.filter(session_key=self.user_id, game=self.question.round.game).first()
            except Exception:
                participant = None
            update_score(participant, self.question, self, self.bet_used)


# Auto-mark answers for choice questions when correct_answer is set/updated
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Question)
def auto_mark_answers_on_correct_answer(sender, instance, created, **kwargs):
    # Only for choice questions with a non-empty correct_answer
    try:
        if instance.type != Question.TYPE_CHOICE or not instance.correct_answer:
            return
    except Exception:
        return

    # find answers for this question that are not yet moderated
    qs = Answer.objects.filter(question=instance, is_correct__isnull=True)
    if not qs.exists():
        return

    # Mark answers whose text matches correct_answer (case-insensitive) as correct
    matches = qs.filter(answer_text__iexact=instance.correct_answer)
    from .utils import update_score
    for a in matches:
        a.is_correct = True
        a.save()  # Answer.save will call update_score if needed
    # Mark remaining unmoderated answers for this question as incorrect
    non_matches = qs.exclude(pk__in=matches.values_list('pk', flat=True))
    for a in non_matches:
        a.is_correct = False
        a.save()
