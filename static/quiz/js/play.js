(function(){
  const cfg = window.PLAY_CONFIG || {};
  const wsUrl = cfg.ws_url;
  const participantId = cfg.participant_id || null;

  const statusEl = document.getElementById('ws-status');
  const questionsContainer = document.getElementById('questions-container');
  const noQuestion = document.getElementById('no-question');
  // safe references for elements that may be absent after template changes
  const countdownEl = document.getElementById('countdown');
  const optionsEl = document.getElementById('options');

  let ws = null;
  let countdownTimer = null;
  let activeQuestions = {}; // map question_id -> question data

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
    } else if (msg.type === 'show_round') {
      showRound(msg.round);
    } else if (msg.type === 'stop_answers') {
      stopAnswers();
    } else if (msg.type === 'player_submit') {
      // optionally show who submitted
      console.log('player_submit', msg);
    }
  }

  function showRound(round) {
    // render whole answer sheet for the round
    if (!round) return;
    // clear any existing
    activeQuestions = {};
    questionsContainer.innerHTML = '';
    noQuestion.classList.add('hidden');
    // title
    const header = document.createElement('h3'); header.innerText = 'Раунд: ' + (round.title || '');
    questionsContainer.appendChild(header);

    (round.questions || []).forEach((q, idx) => {
      activeQuestions[q.id] = q;
      const row = document.createElement('div'); row.className = 'sheet-row'; row.style.marginBottom='8px';
      const label = document.createElement('div'); label.innerText = (idx+1) + '.'; label.style.display='inline-block'; label.style.width='24px';
      row.appendChild(label);
      const container = document.createElement('div'); container.style.display='inline-block'; container.style.verticalAlign='top'; container.style.width='80%';
      if (q.type === 'choice') {
        const opts = document.createElement('div'); opts.className='options';
        (q.options || []).forEach(opt => { const b=document.createElement('button'); b.type='button'; b.innerText=opt; b.dataset.value=opt; b.style.marginRight='6px'; b.addEventListener('click', ()=>{ Array.from(opts.children).forEach(c=>c.classList.remove('selected')); b.classList.add('selected'); }); opts.appendChild(b); });
        container.appendChild(opts);
      } else {
        const inp=document.createElement('input'); inp.type='text'; inp.style.width='100%'; inp.className='open-answer-input'; container.appendChild(inp);
      }
      // bet hidden
      if (q.allow_bet) {
        const bh = document.createElement('input'); bh.type='hidden'; bh.className='bet-hidden'; bh.value = 0; container.appendChild(bh);
        const br = document.createElement('div'); br.style.display='inline-block'; br.style.marginLeft='8px';
        // create checkboxes for +1 and +2 but enforce single selection
        const cb1 = document.createElement('input'); cb1.type='checkbox'; cb1.className='bet-checkbox'; cb1.dataset.value = '1'; cb1.id = 'bet1_' + q.id;
        const lb1 = document.createElement('label'); lb1.htmlFor = cb1.id; lb1.innerText = '+1'; lb1.style.marginRight = '8px';
        const cb2 = document.createElement('input'); cb2.type='checkbox'; cb2.className='bet-checkbox'; cb2.dataset.value = '2'; cb2.id = 'bet2_' + q.id;
        const lb2 = document.createElement('label'); lb2.htmlFor = cb2.id; lb2.innerText = '+2'; lb2.style.marginRight = '8px';
        cb1.addEventListener('change', () => { if (cb1.checked) { cb2.checked = false; bh.value = 1; } else { bh.value = 0; } });
        cb2.addEventListener('change', () => { if (cb2.checked) { cb1.checked = false; bh.value = 2; } else { bh.value = 0; } });
        br.appendChild(cb1); br.appendChild(lb1); br.appendChild(cb2); br.appendChild(lb2);
        container.appendChild(br);
      }
      row.appendChild(container);
      questionsContainer.appendChild(row);
    });

    // Save all button
    const saveAllWrap = document.createElement('div'); saveAllWrap.style.marginTop='12px'; const saveAllBtn=document.createElement('button'); saveAllBtn.type='button'; saveAllBtn.innerText='Сохранить ответы'; saveAllBtn.style.padding='10px 20px'; saveAllBtn.addEventListener('click', ()=>{
      // collect all answers
      const answers = [];
      (round.questions || []).forEach(q => {
        const card = questionsContainer.querySelector('[data-qid="' + q.id + '"]');
      });
      // simplified collection: find rows in order
      const rows = questionsContainer.querySelectorAll('.sheet-row');
      (round.questions || []).forEach((q, idx) => {
        const row = rows[idx];
        const open = row.querySelector('.open-answer-input');
        const sel = row.querySelector('.options button.selected');
        const betHidden = row.querySelector('.bet-hidden');
        const answer = sel ? sel.dataset.value : (open ? open.value.trim() : '');
        const bet = betHidden ? Number(betHidden.value || 0) : 0;
        answers.push({question_id: q.id, answer: answer, bet: bet});
      });
      const payload = {action: 'save_round_answers', answers: answers, participant_id: participantId};
      try { if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(payload)); alert('Ответы сохранены'); } else alert('Нет соединения'); } catch(e){console.error(e);}
    }); saveAllWrap.appendChild(saveAllBtn); questionsContainer.appendChild(saveAllWrap);

    // prefill saved answers if provided (server includes saved_answers when sending show_round on connect)
    if (round.saved_answers) {
      const rows = questionsContainer.querySelectorAll('.sheet-row');
      (round.questions || []).forEach((q, idx) => {
        const data = round.saved_answers[q.id];
        if (!data) return;
        const row = rows[idx];
        if (!row) return;
        if (data.answer_text) {
          const open = row.querySelector('.open-answer-input'); if (open) open.value = data.answer_text;
          const opts = row.querySelectorAll('.options button'); if (opts.length) { Array.from(opts).forEach(b=>{ if (b.dataset.value === data.answer_text) b.classList.add('selected'); }); }
        }
        if (data.bet_used) {
          const bh = row.querySelector('.bet-hidden'); if (bh) bh.value = data.bet_used;
        }
      });
    }
  }

  function showQuestion(msg) {
    // each show_question message represents one question to be added to participant's screen
    const q = msg.question || msg;
    if (!q || !q.id) return;
    // append if not already present
    if (activeQuestions[q.id]) return;
    activeQuestions[q.id] = q;

    // disable iframe clicks while any questions are active
    setIframePointer(false);
    noQuestion.classList.add('hidden');

    const card = document.createElement('div');
    card.className = 'question-card';
    card.dataset.qid = q.id;
    card.style.border = '1px solid #eee';
    card.style.padding = '8px';
    card.style.marginBottom = '8px';

    const title = document.createElement('div');
    title.className = 'question-text';
    title.innerText = q.text || '';
    card.appendChild(title);

    const controls = document.createElement('div');
    controls.className = 'question-controls';

    if (q.type === 'choice') {
      const opts = document.createElement('div');
      opts.className = 'options';
      (q.options || []).forEach(opt => {
        const b = document.createElement('button');
        b.type = 'button'; b.innerText = opt; b.dataset.value = opt; b.style.cursor = 'pointer';
        b.addEventListener('click', (e) => { e.stopPropagation(); Array.from(opts.children).forEach(c=>c.classList.remove('selected')); b.classList.add('selected'); });
        opts.appendChild(b);
      });
      controls.appendChild(opts);
    } else {
      const inp = document.createElement('input');
      inp.type = 'text'; inp.style.width = '100%'; inp.placeholder = 'Введите ответ'; inp.className = 'open-answer-input';
      controls.appendChild(inp);
    }

    // bet controls
    if (q.allow_bet) {
      const betWrap = document.createElement('div'); betWrap.className = 'bet';
      const hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.className = 'bet-hidden'; hidden.value = 0;
      const cb1 = document.createElement('input'); cb1.type = 'checkbox'; cb1.className = 'bet-checkbox'; cb1.dataset.value = '1'; cb1.id = 'bet_q1_' + q.id;
      const lb1 = document.createElement('label'); lb1.htmlFor = cb1.id; lb1.innerText = '+1'; lb1.style.marginRight = '8px';
      const cb2 = document.createElement('input'); cb2.type = 'checkbox'; cb2.className = 'bet-checkbox'; cb2.dataset.value = '2'; cb2.id = 'bet_q2_' + q.id;
      const lb2 = document.createElement('label'); lb2.htmlFor = cb2.id; lb2.innerText = '+2'; lb2.style.marginRight = '8px';
      cb1.addEventListener('change', (e) => { e.stopPropagation(); if (cb1.checked) { cb2.checked = false; hidden.value = 1; } else { hidden.value = 0; } });
      cb2.addEventListener('change', (e) => { e.stopPropagation(); if (cb2.checked) { cb1.checked = false; hidden.value = 2; } else { hidden.value = 0; } });
      betWrap.appendChild(cb1); betWrap.appendChild(lb1); betWrap.appendChild(cb2); betWrap.appendChild(lb2); betWrap.appendChild(hidden);
      controls.appendChild(betWrap);
    }

    const saveWrap = document.createElement('div'); saveWrap.style.marginTop='8px';
    const saveBtn = document.createElement('button'); saveBtn.type='button'; saveBtn.innerText='Сохранить'; saveBtn.style.cursor='pointer';
    const savedLabel = document.createElement('span'); savedLabel.style.marginLeft='8px'; savedLabel.innerText='';
    saveBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // collect answer
      let answer = null;
      if (q.type === 'choice') {
        const sel = card.querySelector('.options button.selected');
        if (!sel) { alert('Выберите вариант'); return; }
        answer = sel.dataset.value;
      } else {
        const inp = card.querySelector('.open-answer-input');
        answer = (inp && inp.value) ? inp.value.trim() : '';
        if (!answer) { alert('Введите ответ'); return; }
      }
      const betHidden = card.querySelector('.bet-hidden');
      const bet = (betHidden && betHidden.value) ? Number(betHidden.value) : 0;

      const payload = { action: 'save_answer', question_id: q.id, answer: answer, bet: bet, participant_id: participantId };
      try {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(payload));
          savedLabel.innerText = 'Сохранено';
          savedLabel.style.color = 'green';
        } else {
          alert('Соединение недоступно');
        }
      } catch (err) { console.error('send error', err); }
    });
    saveWrap.appendChild(saveBtn); saveWrap.appendChild(savedLabel);
    controls.appendChild(saveWrap);

    card.appendChild(controls);
    questionsContainer.appendChild(card);
  }

  function selectOption(btn) {
    if (!inputsEnabled) return;
    // mark selected
    Array.from(optionsEl.children).forEach(c => c.classList.remove('selected'));
    btn.classList.add('selected');
  }

  function stopAnswers() {
    inputsEnabled = false;
    // clear questions from participant screens when round stops
    activeQuestions = {};
    questionsContainer.innerHTML = '';
    noQuestion.classList.remove('hidden');
    // re-enable iframe interactions when answers are stopped
    setIframePointer(true);
  }

  function setIframePointer(enable) {
    try {
      // Use a transparent overlay to block clicks instead of modifying iframe pointer-events.
      const overlay = document.getElementById('video-overlay');
      if (overlay) {
        overlay.style.display = enable ? 'none' : 'block';
      } else {
        // fallback to iframe style if overlay missing
        const iframe = document.querySelector('.video-wrap iframe');
        if (iframe) iframe.style.pointerEvents = enable ? 'auto' : 'none';
      }
    } catch (e) { console.warn('video overlay control failed', e); }
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

  // No global submit button anymore; each question has its own Save.

  // start
  connect();

})();
