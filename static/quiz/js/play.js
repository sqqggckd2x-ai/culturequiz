(function(){
  const cfg = window.PLAY_CONFIG || {};
  const wsUrl = cfg.ws_url;
  const participantId = cfg.participant_id || null;

  const statusEl = document.getElementById('ws-status');
  const questionBox = document.getElementById('question-box');
  const noQuestion = document.getElementById('no-question');
  const questionText = document.getElementById('question-text');
  const optionsEl = document.getElementById('options');
  const openInput = document.getElementById('open-input');
  const openAnswer = document.getElementById('open-answer');
  const submitBtn = document.getElementById('submit-btn');
  const countdownEl = document.getElementById('countdown');
  const betArea = document.getElementById('bet-area');
  const betInput = document.getElementById('bet-input');
  const maxBetEl = document.getElementById('max-bet');

  let ws = null;
  let countdownTimer = null;
  let currentQuestion = null;
  let inputsEnabled = true;

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      statusEl.innerText = 'подключено';
      // send join message with participant id
      ws.send(JSON.stringify({action: 'join_game', participant_id: participantId}));
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        handleMessage(data);
      } catch (err) { console.error('Invalid message', err); }
    };

    ws.onclose = () => {
      statusEl.innerText = 'отключено';
      // try reconnect
      setTimeout(connect, 2000);
    };
  }

  function handleMessage(msg) {
    if (msg.type === 'show_question') {
      showQuestion(msg);
    } else if (msg.type === 'stop_answers') {
      stopAnswers();
    } else if (msg.type === 'player_submit') {
      // optionally show who submitted
      console.log('player_submit', msg);
    }
  }

  function showQuestion(msg) {
    currentQuestion = msg.question || msg;
    // expected fields: id, text, type, options (array), time (seconds), allow_bet, max_bet
    questionText.innerText = currentQuestion.text || '';
    optionsEl.innerHTML = '';
    openAnswer.value = '';

    if (currentQuestion.type === 'choice') {
      openInput.classList.add('hidden');
      optionsEl.classList.remove('hidden');
      (currentQuestion.options || []).forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.innerText = opt;
        btn.dataset.value = opt;
        btn.onclick = () => selectOption(btn);
        optionsEl.appendChild(btn);
      });
    } else {
      optionsEl.classList.add('hidden');
      openInput.classList.remove('hidden');
    }

    if (currentQuestion.allow_bet) {
      betArea.classList.remove('hidden');
      const max = currentQuestion.max_bet || 10;
      betInput.max = max;
      maxBetEl.innerText = `/ max ${max}`;
    } else {
      betArea.classList.add('hidden');
    }

    noQuestion.classList.add('hidden');
    questionBox.classList.remove('hidden');
    inputsEnabled = true;
    // re-query controls (in case DOM changed) and re-enable them
    const _submit = document.getElementById('submit-btn');
    const _openAnswer = document.getElementById('open-answer');
    if (_submit) { _submit.disabled = false; _submit.removeAttribute('disabled'); }
    if (_openAnswer) { _openAnswer.disabled = false; }
    // remove disabled/selected classes from previous options and enable them
    Array.from(optionsEl.children).forEach(c => { c.classList.remove('disabled', 'selected'); c.disabled = false; });
    // ensure submit handler is attached (rebind to be safe on mobile)
    if (_submit) {
      try { _submit.removeEventListener('click', handleSubmitClick); } catch(e) {}
      _submit.addEventListener('click', handleSubmitClick);
    }

    // start countdown
    startCountdown(currentQuestion.time || 30);
  }

  function selectOption(btn) {
    if (!inputsEnabled) return;
    // mark selected
    Array.from(optionsEl.children).forEach(c => c.classList.remove('selected'));
    btn.classList.add('selected');
  }

  function stopAnswers() {
    inputsEnabled = false;
    submitBtn.disabled = true;
    Array.from(optionsEl.children).forEach(c => c.classList.add('disabled'));
    openAnswer.disabled = true;
    clearCountdown();
  }

  function startCountdown(seconds) {
    clearCountdown();
    let rem = seconds;
    countdownEl.innerText = rem + 's';
    countdownTimer = setInterval(() => {
      rem -= 1;
      countdownEl.innerText = rem + 's';
      if (rem <= 0) {
        clearCountdown();
        stopAnswers();
      }
    }, 1000);
  }

  function clearCountdown() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
    countdownEl.innerText = '';
  }

  // named submit handler so we can re-bind on mobile reliably
  function handleSubmitClick() {
    if (!inputsEnabled || !currentQuestion) return;

    let answer = null;
    if (currentQuestion.type === 'choice') {
      const sel = Array.from(optionsEl.children).find(c => c.classList.contains('selected'));
      if (!sel) { alert('Выберите вариант'); return; }
      answer = sel.dataset.value;
    } else {
      answer = openAnswer.value.trim();
      if (!answer) { alert('Введите ответ'); return; }
    }

    const bet = currentQuestion.allow_bet ? Number(betInput.value || 0) : null;

    const payload = {
      action: 'submit_answer',
      question_id: currentQuestion.id,
      answer: answer,
      bet: bet,
      participant_id: participantId,
    };

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
    // optionally disable until server confirms
    stopAnswers();
  }

  // attach initial handler
  if (submitBtn) {
    submitBtn.addEventListener('click', handleSubmitClick);
  }

  // start
  connect();

})();
