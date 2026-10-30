let cachedCampusMapSvg = '';

// Animation setting
const ANIMATIONS_STORAGE_KEY = 'animations_enabled';

function areAnimationsEnabled() {
    const stored = localStorage.getItem(ANIMATIONS_STORAGE_KEY);
    if (stored !== null) return stored === 'true';
    // Without an explicit setting, follow the system "reduce motion" preference: no intro zoom, no animations.
    return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}

function applyAnimationsPreference() {
    if (!document.body) return;
    document.body.classList.toggle('no-animations', !areAnimationsEnabled());
}

// Apply as early as possible to avoid flicker on load.
if (document.body) {
    applyAnimationsPreference();
} else {
    document.addEventListener('DOMContentLoaded', applyAnimationsPreference, { once: true });
}

// Render quiz content, dispatched by type.
function renderQuizBody(quiz) {
    if (quiz.content.type === 'memory') return renderMemoryBody(quiz);
    if (quiz.content.type === 'sort') return renderSortBody(quiz);
    if (quiz.content.type === 'imageGrid') return renderImageGridBody(quiz);
    if (quiz.content.type === 'wordsearch') return renderWordSearchBody(quiz);
    if (quiz.content.type === 'hotspot') return renderHotspotBody(quiz);
    if (quiz.content.type === 'crossword') return renderCrosswordBody(quiz);
    return renderChoiceBody(quiz);
}

// Crossword container; grid and clues are filled in initCrossword.
function renderCrosswordBody(quiz) {
    return `
        <div class="quiz-container crossword-container" data-quiz-id="${quiz.id}" data-quiz-type="crossword">
            <p class="quiz-question">${quiz.content.question}</p>
            <div class="crossword-grid-wrapper">
                <div class="crossword-grid"></div>
            </div>
            <div class="crossword-clues">
                <div class="crossword-clues-section">
                    <h3 class="crossword-clues-title">${t('cw.across')}</h3>
                    <ol class="crossword-clue-list crossword-clues-across"></ol>
                </div>
                <div class="crossword-clues-section">
                    <h3 class="crossword-clues-title">${t('cw.down')}</h3>
                    <ol class="crossword-clue-list crossword-clues-down"></ol>
                </div>
            </div>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
            <div class="quiz-actions">
                <button type="button" class="btn btn-primary quiz-submit-btn">${t('quiz.check')}</button>
                <button type="button" class="btn btn-outline-secondary quiz-reset-btn" style="display:none;">${t('quiz.retry')}</button>
            </div>
        </div>
    `;
}

// Image hotspot: the user clicks spots in the image.
function renderHotspotBody(quiz) {
    const c = quiz.content;
    return `
        <div class="quiz-container hotspot-container" data-quiz-id="${quiz.id}" data-quiz-type="hotspot">
            <p class="quiz-question">${c.question}</p>
            <div class="hotspot-progress">${t('quiz.found', { n: 0, total: c.hotspots.length })}</div>
            <div class="hotspot-image-wrapper">
                <img src="${c.image}" alt="${c.imageAlt || ''}" class="hotspot-image" draggable="false">
                <div class="hotspot-overlay"></div>
            </div>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
            <div class="quiz-actions">
                <button type="button" class="btn btn-sm btn-outline-secondary quiz-reset-btn">
                    <i class="fas fa-redo me-1"></i>${t('quiz.restart')}
                </button>
            </div>
        </div>
    `;
}

// Word search container; grid is filled in initWordSearch.
function renderWordSearchBody(quiz) {
    return `
        <div class="quiz-container wordsearch-container" data-quiz-id="${quiz.id}" data-quiz-type="wordsearch">
            <p class="quiz-question">${quiz.content.question}</p>
            <div class="wordsearch-grid" role="grid"></div>
            <div class="wordsearch-progress"></div>
            <div class="wordsearch-words"></div>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
            <div class="quiz-actions">
                <button type="button" class="btn btn-sm btn-warning wordsearch-hint-btn">
                    <i class="fas fa-lightbulb me-1" aria-hidden="true"></i>${t('ws.hint')}
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary quiz-reset-btn">
                    <i class="fas fa-redo me-1"></i>${t('quiz.restart')}
                </button>
            </div>
        </div>
    `;
}

// Image grid (multi-select); uses the same evaluation logic as checkbox.
function renderImageGridBody(quiz) {
    const c = quiz.content;
    const cols = c.columns || 3;
    const groupName = `quiz-${quiz.id}`;

    const optionsHTML = c.options.map((opt, idx) => `
        <label class="quiz-option quiz-option-image" title="${opt.label || ''}">
            <input type="checkbox" name="${groupName}" value="${idx}" aria-label="${opt.label || ''}">
            <span class="quiz-option-marker" aria-hidden="true"><i class="fas fa-check"></i></span>
            <img src="${opt.image}" alt="" class="quiz-option-img">
        </label>
    `).join('');

    return `
        <div class="quiz-container" data-quiz-id="${quiz.id}" data-quiz-type="imageGrid">
            <p class="quiz-question">${c.question}</p>
            <div class="quiz-image-grid" style="grid-template-columns: repeat(${cols}, 1fr);">${optionsHTML}</div>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
            <div class="quiz-actions">
                <button type="button" class="btn btn-primary quiz-submit-btn">${t('quiz.check')}</button>
                <button type="button" class="btn btn-outline-secondary quiz-reset-btn" style="display:none;">${t('quiz.retry')}</button>
            </div>
        </div>
    `;
}

// Single/multi choice with card styling.
function renderChoiceBody(quiz) {
    const c = quiz.content;
    const inputType = c.type === 'radio' ? 'radio' : 'checkbox';
    const groupName = `quiz-${quiz.id}`;

    const optionsHTML = c.options.map((opt, idx) => `
        <label class="quiz-option">
            <input type="${inputType}" name="${groupName}" value="${idx}">
            <span class="quiz-option-marker"><i class="fas fa-check"></i></span>
            <span class="quiz-option-text">${opt.text}</span>
        </label>
    `).join('');

    return `
        <div class="quiz-container" data-quiz-id="${quiz.id}" data-quiz-type="${c.type}">
            <p class="quiz-question">${c.question}</p>
            <div class="quiz-options">${optionsHTML}</div>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
            <div class="quiz-actions">
                <button type="button" class="btn btn-primary quiz-submit-btn">${t('quiz.check')}</button>
                <button type="button" class="btn btn-outline-secondary quiz-reset-btn" style="display:none;">${t('quiz.retry')}</button>
            </div>
        </div>
    `;
}

// Sort quiz; items are shuffled in initSortQuiz and dragged via SortableJS.
function renderSortBody(quiz) {
    return `
        <div class="quiz-container sort-container" data-quiz-id="${quiz.id}" data-quiz-type="sort">
            <p class="quiz-question">${quiz.content.question}</p>
            <ul class="sort-list" role="list"></ul>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
            <div class="quiz-actions">
                <button type="button" class="btn btn-primary quiz-submit-btn">${t('quiz.check')}</button>
                <button type="button" class="btn btn-outline-secondary quiz-reset-btn" style="display:none;">${t('quiz.retry')}</button>
            </div>
        </div>
    `;
}

// Memory board; cards are shuffled and filled in initMemoryGame.
function renderMemoryBody(quiz) {
    const total = quiz.content.pairs.length;
    return `
        <div class="quiz-container memory-container" data-quiz-id="${quiz.id}" data-quiz-type="memory">
            <div class="memory-status">
                <span class="memory-progress">${t('memory.pairs', { n: 0, total })}</span>
                <button type="button" class="btn btn-sm btn-outline-secondary memory-reset-btn">
                    <i class="fas fa-redo me-1"></i>${t('memory.reshuffle')}
                </button>
            </div>
            <div class="memory-grid"></div>
            <div class="quiz-feedback" role="status" aria-live="polite"></div>
        </div>
    `;
}

// Template function for quiz modals.
function generateQuizModals() {
    const container = document.getElementById('quizModalsContainer');
    quizModals.forEach(quiz => {
        const modalId = `${quiz.id}_modal`;
        const labelId = `${quiz.id}_Label`;
        let campusInfoContent = '';
        if (quiz.campusInfo.hasAccordion) {
            campusInfoContent = `<div class="accordion" id="campusAccordionOverlay">${quiz.campusInfo.accordionItems.map(item => `<div class="accordion-item"><h3 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${item.id}Overlay">${item.title}</button></h3><div id="${item.id}Overlay" class="accordion-collapse collapse" data-bs-parent="#campusAccordionOverlay"><div class="accordion-body"><p>${item.text}</p>${item.link ? `<a href="${item.link.url}" target="_blank" class="erkundungstour-btn"><p>${item.link.text}</p></a>` : ''}</div></div></div>`).join('')}</div>`;
        } else if (quiz.campusInfo.hasMultipleLinks) {
            campusInfoContent = quiz.campusInfo.items.map(item => `<p${item.className ? ` class="${item.className}"` : ''}>${item.text}</p>${item.link ? `<a href="${item.link.url}" target="_blank" class="erkundungstour-btn"><p>${item.link.text}</p></a>` : ''}`).join('');
        } else {
            campusInfoContent = `<p>${quiz.campusInfo.text}</p>${quiz.campusInfo.link ? `<a href="${quiz.campusInfo.link.url}" target="_blank" class="erkundungstour-btn"><p>${quiz.campusInfo.link.text}</p></a>` : ''}`;
        }

        const bodyContent = renderQuizBody(quiz);

        container.insertAdjacentHTML('beforeend', `<div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${labelId}" aria-hidden="true"><div class="modal-dialog modal-dialog-centered modal-fullscreen-md-down modal-lg"><div class="modal-content"><div class="modal-header"><h2 id="${labelId}" class="modal-title">${quiz.title}</h2><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${t('quiz.close')}"></button></div><div class="modal-body frageModalBody${quiz.bodyClass ? ' ' + quiz.bodyClass : ''}">${quiz.description ? `<p class="quiz-question">${quiz.description}</p>` : ''}${bodyContent}</div><div class="campus-info-overlay"><div class="info-icon-trigger" data-bs-toggle="collapse" data-bs-target="#campusInfosOverlay" aria-expanded="false"><i class="fas fa-info-circle campus-info-icon"></i></div><div class="collapse mt-2" id="campusInfosOverlay"><div class="card campus-info-card"><div class="card-body p-2">${campusInfoContent}</div></div></div></div></div></div></div>`);
    });
}
generateQuizModals();

// --- Quiz engine: selection, evaluation, reset ---
function updateQuizOptionStates(container) {
    container.querySelectorAll('.quiz-option').forEach(opt => {
        const input = opt.querySelector('input');
        opt.classList.toggle('selected', input.checked);
    });
}

function evaluateQuiz(container) {
    if (container.dataset.quizType === 'sort') {
        evaluateSortQuiz(container);
        return;
    }
    if (container.dataset.quizType === 'crossword') {
        evaluateCrossword(container);
        return;
    }
    const quizId = container.dataset.quizId;
    const quiz = quizModals.find(q => q.id === quizId);
    if (!quiz?.content) return;

    const options = Array.from(container.querySelectorAll('.quiz-option'));
    const allCorrect = options.every((opt, idx) => {
        const input = opt.querySelector('input');
        const expected = quiz.content.options[idx].correct;
        return input.checked === expected;
    });

    options.forEach((opt, idx) => {
        const input = opt.querySelector('input');
        const expected = quiz.content.options[idx].correct;
        opt.classList.add('locked');
        if (allCorrect) {
            if (expected) opt.classList.add('correct');
        } else {
            if (!expected && input.checked) {
                opt.classList.add('incorrect');
                const icon = opt.querySelector('.quiz-option-marker i');
                if (icon) { icon.classList.remove('fa-check'); icon.classList.add('fa-times'); }
            }
        }
    });

    const feedback = container.querySelector('.quiz-feedback');
    const submitBtn = container.querySelector('.quiz-submit-btn');
    const resetBtn = container.querySelector('.quiz-reset-btn');

    if (allCorrect) {
        const msg = quiz.content.successMessage || t('quiz.correct');
        feedback.className = 'quiz-feedback show success';
        feedback.innerHTML = `<i class="fas fa-check-circle me-2"></i>${msg}`;
        submitBtn.style.display = 'none';
        resetBtn.style.display = 'none';
        if (addCompletedQuizId(quizId)) showBadgeNotification();
    } else {
        feedback.className = 'quiz-feedback show error';
        feedback.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('quiz.wrong')}`;
        submitBtn.style.display = 'none';
        resetBtn.style.display = 'inline-block';
    }
}

function resetQuiz(container) {
    if (container.dataset.quizType === 'memory') {
        initMemoryGame(container);
        return;
    }
    if (container.dataset.quizType === 'sort') {
        initSortQuiz(container);
        return;
    }
    if (container.dataset.quizType === 'wordsearch') {
        initWordSearch(container);
        return;
    }
    if (container.dataset.quizType === 'hotspot') {
        initHotspotQuiz(container);
        return;
    }
    if (container.dataset.quizType === 'crossword') {
        initCrossword(container);
        return;
    }
    container.querySelectorAll('.quiz-option').forEach(opt => {
        opt.classList.remove('selected', 'correct', 'incorrect', 'locked');
        const input = opt.querySelector('input');
        if (input) input.checked = false;
        const icon = opt.querySelector('.quiz-option-marker i');
        if (icon) { icon.classList.remove('fa-times'); icon.classList.add('fa-check'); }
    });
    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback';
    feedback.innerHTML = '';
    container.querySelector('.quiz-submit-btn').style.display = 'inline-block';
    container.querySelector('.quiz-reset-btn').style.display = 'none';
}

// --- Sort quiz (drag and drop) ---
function initSortQuiz(container) {
    const quizId = container.dataset.quizId;
    const quiz = quizModals.find(q => q.id === quizId);
    if (!quiz?.content?.items) return;

    const correctItems = quiz.content.items;
    // Shuffle, making sure the result is not the original order.
    let shuffledIdx;
    do {
        shuffledIdx = correctItems.map((_, i) => i);
        for (let i = shuffledIdx.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffledIdx[i], shuffledIdx[j]] = [shuffledIdx[j], shuffledIdx[i]];
        }
    } while (correctItems.length > 1 && shuffledIdx.every((v, i) => v === i));

    const list = container.querySelector('.sort-list');
    list.innerHTML = shuffledIdx.map(originalIdx => `
        <li class="sort-item" data-correct-idx="${originalIdx}">
            <span class="sort-handle" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
            <span class="sort-text">${correctItems[originalIdx]}</span>
            <span class="sort-arrows">
                <button type="button" class="sort-arrow-btn" data-direction="up" aria-label="${t('sort.up', { item: correctItems[originalIdx] })}">
                    <i class="fas fa-chevron-up"></i>
                </button>
                <button type="button" class="sort-arrow-btn" data-direction="down" aria-label="${t('sort.down', { item: correctItems[originalIdx] })}">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </span>
        </li>
    `).join('');

    // Destroy an existing Sortable instance on reshuffle.
    if (container._sortable) {
        try { container._sortable.destroy(); } catch (e) {}
        container._sortable = null;
    }

    if (typeof Sortable !== 'undefined') {
        container._sortable = Sortable.create(list, {
            animation: 150,
            handle: '.sort-item',
            filter: '.sort-arrow-btn',
            preventOnFilter: true,
            ghostClass: 'sort-ghost',
            chosenClass: 'sort-chosen',
            dragClass: 'sort-drag',
            forceFallback: false,
            fallbackTolerance: 3,
            touchStartThreshold: 3,
            onSort: () => updateSortArrowStates(container)
        });
    }

    container.querySelectorAll('.sort-item').forEach(li => {
        li.classList.remove('correct', 'incorrect', 'locked');
    });
    updateSortArrowStates(container);
    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback';
    feedback.innerHTML = '';
    container.querySelector('.quiz-submit-btn').style.display = 'inline-block';
    container.querySelector('.quiz-reset-btn').style.display = 'none';
}

function updateSortArrowStates(container) {
    const items = Array.from(container.querySelectorAll('.sort-item'));
    items.forEach((li, idx) => {
        const upBtn = li.querySelector('.sort-arrow-btn[data-direction="up"]');
        const downBtn = li.querySelector('.sort-arrow-btn[data-direction="down"]');
        if (upBtn) upBtn.disabled = idx === 0;
        if (downBtn) downBtn.disabled = idx === items.length - 1;
    });
}

function moveSortItem(item, direction) {
    const list = item.parentNode;
    if (!list) return;
    if (direction === 'up') {
        const prev = item.previousElementSibling;
        if (prev) list.insertBefore(item, prev);
    } else if (direction === 'down') {
        const next = item.nextElementSibling;
        if (next) list.insertBefore(next, item);
    }
    item.classList.remove('sort-bump');
    // Force a reflow so the animation restarts.
    void item.offsetWidth;
    item.classList.add('sort-bump');
    const container = item.closest('.sort-container');
    if (container) updateSortArrowStates(container);
}

function evaluateSortQuiz(container) {
    const quizId = container.dataset.quizId;
    const items = Array.from(container.querySelectorAll('.sort-item'));
    let allCorrect = true;

    items.forEach((li, currentIdx) => {
        const expectedIdx = parseInt(li.dataset.correctIdx, 10);
        li.classList.add('locked');
        if (expectedIdx === currentIdx) {
            li.classList.add('correct');
        } else {
            li.classList.add('incorrect');
            allCorrect = false;
        }
    });

    // Disable Sortable during evaluation.
    if (container._sortable) {
        container._sortable.option('disabled', true);
    }

    const feedback = container.querySelector('.quiz-feedback');
    const submitBtn = container.querySelector('.quiz-submit-btn');
    const resetBtn = container.querySelector('.quiz-reset-btn');

    if (allCorrect) {
        feedback.className = 'quiz-feedback show success';
        feedback.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t('sort.correct')}`;
        submitBtn.style.display = 'none';
        resetBtn.style.display = 'none';
        if (addCompletedQuizId(quizId)) showBadgeNotification();
    } else {
        feedback.className = 'quiz-feedback show error';
        feedback.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('sort.wrong')}`;
        submitBtn.style.display = 'none';
        resetBtn.style.display = 'inline-block';
    }
}

// --- Crossword (crossword-layout-generator + custom UI) ---
function initCrossword(container) {
    const quiz = quizModals.find(q => q.id === container.dataset.quizId);
    if (!quiz?.content?.words || typeof generateLayout === 'undefined') {
        const fb = container.querySelector('.quiz-feedback');
        if (fb && typeof generateLayout === 'undefined') {
            fb.className = 'quiz-feedback show error';
            fb.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('cw.libError')}`;
        }
        return;
    }

    const wordsJson = quiz.content.words.map(w => ({
        clue: w.clue,
        answer: w.answer.toUpperCase()
    }));

    const layout = generateLayout(wordsJson);
    container._crosswordLayout = layout;

    renderCrosswordGrid(container, layout);
    renderCrosswordClues(container, layout);
    setupCrosswordInput(container);

    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback';
    feedback.innerHTML = '';
    container.querySelector('.quiz-submit-btn').style.display = 'inline-block';
    container.querySelector('.quiz-reset-btn').style.display = 'none';
}

function renderCrosswordGrid(container, layout) {
    const grid = container.querySelector('.crossword-grid');
    grid.style.gridTemplateColumns = `repeat(${layout.cols}, var(--cw-cell-size, 38px))`;

    // Fit the cell size to the modal width to avoid horizontal scroll on desktop.
    const fitCellSize = () => {
        const wrapper = grid.closest('.crossword-grid-wrapper');
        if (!wrapper || !wrapper.clientWidth) return;
        const isMobile = window.innerWidth < 576;
        const idealMax = isMobile ? 36 : 42;
        const minSize = 22;
        const wrapperCs = getComputedStyle(wrapper);
        const gridCs = getComputedStyle(grid);
        const gap = parseFloat(gridCs.columnGap) || 0;
        // Available width minus wrapper padding, grid padding and a 4px buffer.
        const available = wrapper.clientWidth
            - parseFloat(wrapperCs.paddingLeft) - parseFloat(wrapperCs.paddingRight)
            - parseFloat(gridCs.paddingLeft) - parseFloat(gridCs.paddingRight) - 4;
        const fitting = Math.floor((available - (layout.cols - 1) * gap) / layout.cols);
        const size = Math.max(minSize, Math.min(idealMax, fitting));
        grid.style.setProperty('--cw-cell-size', size + 'px');
    };
    requestAnimationFrame(fitCellSize);
    // Recompute on resize.
    if (container._crosswordResize) window.removeEventListener('resize', container._crosswordResize);
    container._crosswordResize = fitCellSize;
    window.addEventListener('resize', container._crosswordResize);

    // Position map: "row,col" → clue number.
    const numberMap = {};
    layout.result.forEach(word => {
        if (word.startx === undefined || word.starty === undefined) return;
        const key = `${word.starty - 1},${word.startx - 1}`;
        if (!numberMap[key] || word.position < numberMap[key]) {
            numberMap[key] = word.position;
        }
    });

    // Per cell: which words pass through it; this yields the screen reader name ("6 across, letter 2 of 9") and the aria-describedby link to the clue.
    const quizId = container.dataset.quizId || 'cw';
    const cellWords = {};
    layout.result.forEach(word => {
        if (word.startx === undefined || word.starty === undefined) return;
        for (let i = 0; i < word.answer.length; i++) {
            const key = `${word.starty - 1 + (word.orientation === 'down' ? i : 0)},${word.startx - 1 + (word.orientation === 'across' ? i : 0)}`;
            (cellWords[key] = cellWords[key] || []).push({ word, i });
        }
    });
    const cellLabel = key => (cellWords[key] || [])
        .map(({ word, i }) => t('cw.cell', { num: word.position, dir: t(word.orientation === 'across' ? 'cw.dirAcross' : 'cw.dirDown'), i: i + 1, n: word.answer.length }))
        .join('; ');
    const cellClueIds = key => (cellWords[key] || [])
        .map(({ word }) => `${quizId}-clue-${word.orientation}-${word.position}`)
        .join(' ');

    let html = '';
    for (let r = 0; r < layout.rows; r++) {
        for (let c = 0; c < layout.cols; c++) {
            const letter = layout.table[r][c];
            if (!letter || letter === '-') {
                html += `<div class="cw-cell cw-cell-empty"></div>`;
            } else {
                const key = `${r},${c}`;
                const number = numberMap[key];
                html += `
                    <div class="cw-cell" data-row="${r}" data-col="${c}" data-letter="${letter.toUpperCase()}">
                        ${number ? `<span class="cw-cell-number">${number}</span>` : ''}
                        <input type="text" maxlength="1" class="cw-cell-input" aria-label="${cellLabel(`${r},${c}`)}" aria-describedby="${cellClueIds(`${r},${c}`)}" autocapitalize="characters" autocomplete="off" inputmode="text">
                    </div>
                `;
            }
        }
    }
    grid.innerHTML = html;
}

function renderCrosswordClues(container, layout) {
    const acrossEl = container.querySelector('.crossword-clues-across');
    const downEl = container.querySelector('.crossword-clues-down');

    const across = layout.result
        .filter(w => w.orientation === 'across')
        .sort((a, b) => a.position - b.position);
    const down = layout.result
        .filter(w => w.orientation === 'down')
        .sort((a, b) => a.position - b.position);

    const quizId = container.dataset.quizId || 'cw';
    const tpl = w => `<li class="cw-clue" id="${quizId}-clue-${w.orientation}-${w.position}" value="${w.position}"><span class="cw-clue-num">${w.position}.</span> ${w.clue}</li>`;
    acrossEl.innerHTML = across.map(tpl).join('');
    downEl.innerHTML = down.map(tpl).join('');
}

function setupCrosswordInput(container) {
    const layout = container._crosswordLayout;
    if (!layout) return;

    // Cell map: "row,col" → DOM element.
    const cellMap = {};
    container.querySelectorAll('.cw-cell:not(.cw-cell-empty)').forEach(cell => {
        cellMap[`${cell.dataset.row},${cell.dataset.col}`] = cell;
    });

    // Per cell: remember which words pass through it and at which position.
    const cellWords = new Map();
    layout.result.forEach(word => {
        if (word.startx === undefined) return;
        for (let i = 0; i < word.answer.length; i++) {
            const r = word.starty - 1 + (word.orientation === 'down' ? i : 0);
            const c = word.startx - 1 + (word.orientation === 'across' ? i : 0);
            const cell = cellMap[`${r},${c}`];
            if (!cell) continue;
            if (!cellWords.has(cell)) cellWords.set(cell, {});
            cellWords.get(cell)[word.orientation] = { word, pos: i };
        }
    });

    // Highlight the active word.
    function highlightActiveWord() {
        container.querySelectorAll('.cw-cell.cw-cell-active').forEach(c => c.classList.remove('cw-cell-active'));
        container.querySelectorAll('.cw-clue.cw-clue-active').forEach(li => li.classList.remove('cw-clue-active'));
        const focusedInput = container.querySelector('.cw-cell-input:focus');
        if (!focusedInput) return;
        const focusedCell = focusedInput.closest('.cw-cell');
        const info = cellWords.get(focusedCell);
        if (!info) return;
        const dir = container._crosswordDir;
        const wordInfo = info[dir] || info.across || info.down;
        if (!wordInfo) return;
        const { word } = wordInfo;
        container.querySelector(`.crossword-clues-${word.orientation} .cw-clue[value="${word.position}"]`)?.classList.add('cw-clue-active');
        for (let i = 0; i < word.answer.length; i++) {
            const r = word.starty - 1 + (word.orientation === 'down' ? i : 0);
            const c = word.startx - 1 + (word.orientation === 'across' ? i : 0);
            const cell = cellMap[`${r},${c}`];
            if (cell) cell.classList.add('cw-cell-active');
        }
    }

    function getNeighborCell(cell, direction, step) {
        const info = cellWords.get(cell);
        if (!info || !info[direction]) return null;
        const { word, pos } = info[direction];
        const newPos = pos + step;
        if (newPos < 0 || newPos >= word.answer.length) return null;
        const r = word.starty - 1 + (direction === 'down' ? newPos : 0);
        const c = word.startx - 1 + (direction === 'across' ? newPos : 0);
        return cellMap[`${r},${c}`];
    }

    container._crosswordDir = 'across';

    container.querySelectorAll('.cw-cell-input').forEach(input => {
        const cell = input.closest('.cw-cell');

        input.addEventListener('focus', () => {
            const info = cellWords.get(cell);
            if (!info) return;
            // If the cell belongs to one direction only, switch to it.
            if (info.across && !info.down) container._crosswordDir = 'across';
            else if (info.down && !info.across) container._crosswordDir = 'down';
            highlightActiveWord();
        });

        // Clicking an already focused crossing cell toggles the direction.
        input.addEventListener('mousedown', () => {
            const info = cellWords.get(cell);
            if (info?.across && info?.down && document.activeElement === input) {
                container._crosswordDir = container._crosswordDir === 'across' ? 'down' : 'across';
                highlightActiveWord();
            }
        });

        input.addEventListener('input', (e) => {
            let val = (e.target.value || '').toUpperCase().replace(/[^A-ZÄÖÜ]/g, '').slice(0, 1);
            e.target.value = val;
            cell.classList.remove('cw-cell-incorrect', 'cw-cell-correct');
            if (val) {
                // Find the next EMPTY cell along the current direction.
                let next = getNeighborCell(cell, container._crosswordDir, 1);
                while (next) {
                    const nextInput = next.querySelector('.cw-cell-input');
                    if (!nextInput.value) {
                        nextInput.focus();
                        break;
                    }
                    next = getNeighborCell(next, container._crosswordDir, 1);
                }
            }
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !e.target.value) {
                e.preventDefault();
                const prev = getNeighborCell(cell, container._crosswordDir, -1);
                if (prev) {
                    const prevInput = prev.querySelector('.cw-cell-input');
                    prevInput.focus();
                    prevInput.value = '';
                    prev.classList.remove('cw-cell-incorrect', 'cw-cell-correct');
                }
                return;
            }
            // Arrow keys navigate and also switch the direction.
            const dirMap = { ArrowRight: ['across', 1], ArrowLeft: ['across', -1], ArrowDown: ['down', 1], ArrowUp: ['down', -1] };
            if (dirMap[e.key]) {
                e.preventDefault();
                const [dir, step] = dirMap[e.key];
                container._crosswordDir = dir;
                const target = getNeighborCell(cell, dir, step);
                if (target) target.querySelector('.cw-cell-input').focus();
                else highlightActiveWord();
            }
        });
    });

    // Clicking a clue jumps to the word's first cell and sets the direction.
    container.querySelectorAll('.cw-clue').forEach(li => {
        li.style.cursor = 'pointer';
        li.addEventListener('click', () => {
            const isAcross = li.closest('.crossword-clues-across') !== null;
            const position = parseInt(li.getAttribute('value'), 10);
            const word = layout.result.find(w => w.position === position && w.orientation === (isAcross ? 'across' : 'down'));
            if (!word) return;
            container._crosswordDir = word.orientation;
            const firstCell = cellMap[`${word.starty - 1},${word.startx - 1}`];
            if (firstCell) firstCell.querySelector('.cw-cell-input').focus();
        });
    });
}

function normalizeCrosswordChar(c) {
    return (c || '').toUpperCase()
        .replace(/Ö/g, 'O').replace(/Ä/g, 'A').replace(/Ü/g, 'U');
}

function evaluateCrossword(container) {
    const cells = Array.from(container.querySelectorAll('.cw-cell:not(.cw-cell-empty)'));
    let allCorrect = true;
    let allFilled = true;

    cells.forEach(cell => {
        const input = cell.querySelector('.cw-cell-input');
        const expected = normalizeCrosswordChar(cell.dataset.letter);
        const got = normalizeCrosswordChar(input.value);
        cell.classList.remove('cw-cell-correct', 'cw-cell-incorrect');
        if (!got) {
            allFilled = false;
            allCorrect = false;
            return;
        }
        if (got === expected) {
            cell.classList.add('cw-cell-correct');
        } else {
            cell.classList.add('cw-cell-incorrect');
            allCorrect = false;
        }
    });

    const feedback = container.querySelector('.quiz-feedback');
    const submitBtn = container.querySelector('.quiz-submit-btn');
    const resetBtn = container.querySelector('.quiz-reset-btn');

    if (allCorrect && allFilled) {
        feedback.className = 'quiz-feedback show success';
        feedback.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t('cw.solved')}`;
        submitBtn.style.display = 'none';
        resetBtn.style.display = 'none';
        cells.forEach(c => {
            const inp = c.querySelector('.cw-cell-input');
            if (inp) inp.disabled = true;
        });
        if (addCompletedQuizId(container.dataset.quizId)) showBadgeNotification();
    } else if (!allFilled) {
        feedback.className = 'quiz-feedback show error';
        feedback.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('cw.missing')}`;
    } else {
        feedback.className = 'quiz-feedback show error';
        feedback.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('cw.wrongLetters')}`;
        resetBtn.style.display = 'inline-block';
    }
}

// --- Image Hotspot ---
function initHotspotQuiz(container) {
    const overlay = container.querySelector('.hotspot-overlay');
    if (!overlay) return;
    overlay.innerHTML = '';
    container._hotspotFound = new Set();

    const quiz = quizModals.find(q => q.id === container.dataset.quizId);
    const hotspots = quiz?.content?.hotspots || [];
    const total = hotspots.length;
    const progressEl = container.querySelector('.hotspot-progress');
    if (progressEl) progressEl.textContent = t('quiz.found', { n: 0, total });

    const feedback = container.querySelector('.quiz-feedback');
    if (feedback) {
        feedback.className = 'quiz-feedback';
        feedback.innerHTML = '';
    }

    // Debug mode: show zones as dashed circles.
    if (quiz?.content?.debug) {
        hotspots.forEach((h, i) => {
            const zone = document.createElement('div');
            zone.className = 'hotspot-debug-zone';
            zone.style.left = `${h.x}%`;
            zone.style.top = `${h.y}%`;
            // Diameter = 2 * radius in % of the image width.
            zone.style.width = `${h.radius * 2}%`;
            zone.style.aspectRatio = '1 / 1';
            zone.title = `[${i}] ${h.label || ''} (x:${h.x}, y:${h.y}, r:${h.radius})`;
            overlay.appendChild(zone);
        });
    }
}

function handleHotspotClick(overlay, evt) {
    const container = overlay.closest('.hotspot-container');
    if (!container) return;
    const quiz = quizModals.find(q => q.id === container.dataset.quizId);
    const hotspots = quiz?.content?.hotspots;
    if (!hotspots) return;

    const rect = overlay.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = ((evt.clientX - rect.left) / rect.width) * 100;
    const y = ((evt.clientY - rect.top) / rect.height) * 100;

    const found = container._hotspotFound || new Set();

    // Ignore clicks on an already found zone.
    for (let i = 0; i < hotspots.length; i++) {
        if (!found.has(i)) continue;
        const h = hotspots[i];
        const dx = x - h.x, dy = y - h.y;
        if (Math.sqrt(dx * dx + dy * dy) <= h.radius) return;
    }

    // Check for a hit on a new hotspot.
    let hitIdx = -1;
    for (let i = 0; i < hotspots.length; i++) {
        if (found.has(i)) continue;
        const h = hotspots[i];
        const dx = x - h.x, dy = y - h.y;
        if (Math.sqrt(dx * dx + dy * dy) <= h.radius) { hitIdx = i; break; }
    }

    if (hitIdx >= 0) {
        const h = hotspots[hitIdx];
        const marker = document.createElement('div');
        marker.className = 'hotspot-marker correct';
        marker.style.left = `${h.x}%`;
        marker.style.top = `${h.y}%`;
        marker.title = h.label || '';
        marker.innerHTML = '<i class="fas fa-check"></i>';
        overlay.appendChild(marker);

        found.add(hitIdx);
        container._hotspotFound = found;

        const progressEl = container.querySelector('.hotspot-progress');
        if (progressEl) progressEl.textContent = t('quiz.found', { n: found.size, total: hotspots.length });

        if (found.size === hotspots.length) completeHotspotQuiz(container);
    } else {
        const marker = document.createElement('div');
        marker.className = 'hotspot-marker incorrect';
        marker.style.left = `${x}%`;
        marker.style.top = `${y}%`;
        marker.innerHTML = '<i class="fas fa-times"></i>';
        overlay.appendChild(marker);
        setTimeout(() => marker.remove(), 850);
    }
}

function completeHotspotQuiz(container) {
    const quizId = container.dataset.quizId;
    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback show success';
    feedback.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t('hotspot.done')}`;
    if (addCompletedQuizId(quizId)) showBadgeNotification();
}

// --- Word search (Wordfind.js + custom click/drag UI) ---
const WORDSEARCH_COLORS = [
    '#c8e6c9', '#ffe0b2', '#c5cae9', '#f8bbd0', '#b2dfdb',
    '#d1c4e9', '#ffccbc', '#fff9c4', '#b3e5fc', '#d7ccc8'
];

const WORDSEARCH_ORIENTATIONS = {
    horizontal: (x, y, i) => ({ x: x + i, y: y }),
    horizontalBack: (x, y, i) => ({ x: x - i, y: y }),
    vertical: (x, y, i) => ({ x: x, y: y + i }),
    verticalUp: (x, y, i) => ({ x: x, y: y - i }),
    diagonal: (x, y, i) => ({ x: x + i, y: y + i }),
    diagonalBack: (x, y, i) => ({ x: x - i, y: y + i }),
    diagonalUp: (x, y, i) => ({ x: x + i, y: y - i }),
    diagonalUpBack: (x, y, i) => ({ x: x - i, y: y - i })
};

function solutionToCells(sol) {
    const fn = WORDSEARCH_ORIENTATIONS[sol.orientation];
    if (!fn) return [];
    const cells = [];
    for (let i = 0; i < sol.word.length; i++) {
        const p = fn(sol.x, sol.y, i);
        cells.push({ row: p.y, col: p.x });
    }
    return cells;
}

function initWordSearch(container) {
    const quiz = quizModals.find(q => q.id === container.dataset.quizId);
    if (!quiz?.content?.words || typeof wordfind === 'undefined') {
        if (typeof wordfind === 'undefined') {
            const fb = container.querySelector('.quiz-feedback');
            if (fb) {
                fb.className = 'quiz-feedback show error';
                fb.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('ws.libError')}`;
            }
        }
        return;
    }

    if (container._wsCleanup) container._wsCleanup();

    const c = quiz.content;
    const width = c.width || 14;
    const height = c.height || 14;
    const searchTerms = c.words.map(w => w.search.toUpperCase());

    let puzzle;
    try {
        puzzle = wordfind.newPuzzle(searchTerms, {
            height: height, width: width,
            fillBlanks: true, preferOverlap: true
        });
    } catch (e) {
        const fb = container.querySelector('.quiz-feedback');
        if (fb) {
            fb.className = 'quiz-feedback show error';
            fb.innerHTML = `<i class="fas fa-times-circle me-2"></i>${t('ws.createError')}`;
        }
        return;
    }

    const solved = wordfind.solve(puzzle, searchTerms);
    const solutionMap = {};
    (solved.found || []).forEach(sol => {
        solutionMap[sol.word.toUpperCase()] = sol;
    });

    container._wsPuzzle = puzzle;
    container._wsSolutions = solutionMap;
    container._wsFoundCount = 0;
    container._wsColorIdx = 0;
    container._wsTotal = c.words.length;
    container._wsHinted = new Set();

    // Render the grid.
    const gridEl = container.querySelector('.wordsearch-grid');
    const actualWidth = puzzle[0].length;
    const actualHeight = puzzle.length;
    gridEl.style.gridTemplateColumns = `repeat(${actualWidth}, 1fr)`;
    // Row wrappers with display:contents keep the cells direct grid items (layout unchanged) while giving the grid the row/cell structure required by role="grid".
    gridEl.innerHTML = puzzle.map((row, r) =>
        `<div class="wordsearch-row" role="row">` + row.map((letter, col) =>
            `<div class="wordsearch-cell" role="gridcell" tabindex="-1" data-row="${r}" data-col="${col}" aria-label="${t('ws.cell', { letter: letter.toUpperCase(), r: r + 1, c: col + 1 })}">${letter.toUpperCase()}</div>`
        ).join('') + `</div>`
    ).join('');
    gridEl.setAttribute('aria-label', t('ws.gridLabel'));

    // Render the word list; add (SEARCH) only when display differs from the search term.
    const wordsEl = container.querySelector('.wordsearch-words');
    wordsEl.innerHTML = c.words.map(w => {
        const search = w.search.toUpperCase();
        const displayUpper = w.display.toUpperCase();
        const displayLabel = displayUpper === search ? search : `${w.display} (${search})`;
        return `<span class="wordsearch-word" data-search="${search}">${displayLabel}</span>`;
    }).join('');

    // Progress
    const progressEl = container.querySelector('.wordsearch-progress');
    progressEl.textContent = t('quiz.found', { n: 0, total: c.words.length });

    // Reset feedback.
    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback';
    feedback.innerHTML = '';

    setupWordSearchInteraction(container);
}

function setupWordSearchInteraction(container) {
    const grid = container.querySelector('.wordsearch-grid');
    let isDragging = false;
    let startCell = null;
    let currentCells = [];

    const getCellFromPoint = (x, y) => {
        const el = document.elementFromPoint(x, y);
        if (!el) return null;
        return el.classList.contains('wordsearch-cell') ? el : null;
    };

    const clearHighlight = () => {
        grid.querySelectorAll('.wordsearch-cell.highlight').forEach(c => c.classList.remove('highlight'));
    };

    const calculateLine = (start, end) => {
        const r1 = +start.dataset.row, c1 = +start.dataset.col;
        const r2 = +end.dataset.row, c2 = +end.dataset.col;
        const diffR = r2 - r1, diffC = c2 - c1;
        const absR = Math.abs(diffR), absC = Math.abs(diffC);
        let dr, dc;
        if (absC > absR * 2.5) { dr = 0; dc = Math.sign(diffC) || 1; }
        else if (absR > absC * 2.5) { dr = Math.sign(diffR) || 1; dc = 0; }
        else { dr = Math.sign(diffR); dc = Math.sign(diffC); }
        if (dr === 0 && dc === 0) return [start];
        const length = Math.max(absR, absC) + 1;
        const cells = [];
        for (let i = 0; i < length; i++) {
            const r = r1 + i * dr;
            const col = c1 + i * dc;
            const cell = grid.querySelector(`.wordsearch-cell[data-row="${r}"][data-col="${col}"]`);
            if (cell) cells.push(cell);
        }
        return cells;
    };

    const highlight = (cells) => {
        clearHighlight();
        cells.forEach(c => c.classList.add('highlight'));
    };

    const onDown = (e) => {
        const cell = getCellFromPoint(e.clientX, e.clientY);
        if (!cell) return;
        // Allow dragging over already found cells (words may cross).
        e.preventDefault();
        isDragging = true;
        startCell = cell;
        currentCells = [cell];
        highlight(currentCells);
    };

    const onMove = (e) => {
        if (!isDragging) return;
        const cell = getCellFromPoint(e.clientX, e.clientY);
        if (!cell) return;
        currentCells = calculateLine(startCell, cell);
        highlight(currentCells);
    };

    const onUp = (e) => {
        if (!isDragging) return;
        isDragging = false;
        if (currentCells.length >= 2) {
            checkWordSearchSelection(container, currentCells);
        }
        clearHighlight();
        startCell = null;
        currentCells = [];
    };

    grid.addEventListener('pointerdown', onDown);
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onUp);

    container._wsCleanup = () => {
        grid.removeEventListener('pointerdown', onDown);
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        document.removeEventListener('pointercancel', onUp);
    };
}

function checkWordSearchSelection(container, selectedCells) {
    const solutions = container._wsSolutions || {};
    const selectedKey = selectedCells.map(c => `${c.dataset.row},${c.dataset.col}`).join('|');
    const reverseKey = [...selectedCells].reverse().map(c => `${c.dataset.row},${c.dataset.col}`).join('|');

    for (const search in solutions) {
        const wordEl = container.querySelector(`.wordsearch-word[data-search="${search}"]`);
        if (!wordEl || wordEl.classList.contains('found')) continue;

        const solCells = solutionToCells(solutions[search]);
        const solKey = solCells.map(p => `${p.row},${p.col}`).join('|');

        if (solKey === selectedKey || solKey === reverseKey) {
            const color = WORDSEARCH_COLORS[container._wsColorIdx % WORDSEARCH_COLORS.length];
            container._wsColorIdx++;

            selectedCells.forEach(cell => {
                // Already found crossing cells keep their original color.
                if (!cell.classList.contains('found-locked')) {
                    cell.style.backgroundColor = color;
                    cell.classList.add('found-locked');
                }
            });
            wordEl.classList.add('found');
            wordEl.style.backgroundColor = color;
            wordEl.style.borderColor = color;

            container._wsFoundCount++;
            const progressEl = container.querySelector('.wordsearch-progress');
            if (progressEl) progressEl.textContent = t('quiz.found', { n: container._wsFoundCount, total: container._wsTotal });

            if (container._wsFoundCount === container._wsTotal) {
                completeWordSearch(container);
            }
            return;
        }
    }
}

function completeWordSearch(container) {
    const quizId = container.dataset.quizId;
    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback show success';
    feedback.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t('ws.done')}`;
    if (addCompletedQuizId(quizId)) showBadgeNotification();
}

function showWordsearchHint(container) {
    const solutions = container._wsSolutions || {};
    const missing = Object.keys(solutions).filter(search => {
        const wordEl = container.querySelector(`.wordsearch-word[data-search="${search}"]`);
        return wordEl && !wordEl.classList.contains('found');
    });
    if (missing.length === 0) return;

    let candidate;
    if (missing.length === 1) {
        // Last remaining word: always show this one.
        candidate = missing[0];
    } else {
        if (!container._wsHinted) container._wsHinted = new Set();
        // Filter out words already hinted in this cycle.
        let pool = missing.filter(w => !container._wsHinted.has(w));
        // If all missing words were hinted, reset the cycle.
        if (pool.length === 0) {
            container._wsHinted.clear();
            pool = missing;
        }
        candidate = pool[Math.floor(Math.random() * pool.length)];
        container._wsHinted.add(candidate);
    }

    const sol = solutions[candidate];
    if (!sol) return;
    const cells = solutionToCells(sol);
    if (!cells.length) return;

    const grid = container.querySelector('.wordsearch-grid');
    grid.querySelectorAll('.wordsearch-cell.hint-flash').forEach(c => c.classList.remove('hint-flash'));

    const firstPos = cells[0];
    const firstCell = grid.querySelector(`.wordsearch-cell[data-row="${firstPos.row}"][data-col="${firstPos.col}"]`);
    if (!firstCell) return;
    // Force a reflow so the animation restarts.
    void firstCell.offsetWidth;
    firstCell.classList.add('hint-flash');
    setTimeout(() => firstCell.classList.remove('hint-flash'), 3000);

    // Briefly highlight the matching word in the list too.
    const wordEl = container.querySelector(`.wordsearch-word[data-search="${candidate}"]`);
    if (wordEl) {
        wordEl.classList.remove('hint-pulse');
        void wordEl.offsetWidth;
        wordEl.classList.add('hint-pulse');
        setTimeout(() => wordEl.classList.remove('hint-pulse'), 3000);
    }
}

// --- Memory game ---
function initMemoryGame(container) {
    const quizId = container.dataset.quizId;
    const quiz = quizModals.find(q => q.id === quizId);
    if (!quiz?.content?.pairs) return;

    const pairs = quiz.content.pairs;
    const deck = [];
    pairs.forEach((pair, idx) => {
        deck.push({ pairId: idx, image: pair.image, label: pair.label || '' });
        deck.push({ pairId: idx, image: pair.image, label: pair.label || '' });
    });
    // Fisher-Yates shuffle
    for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
    }

    const grid = container.querySelector('.memory-grid');
    // <button> instead of <div>: cards are tabbable and react to Enter/Space without extra code; inner <span> because <button> allows only phrasing content.
    const deckHTML = deck.map((card, i) => `
        <button type="button" class="memory-card" data-pair-id="${card.pairId}"
                data-card-label="${card.label}"
                aria-label="${t('memory.cardHidden', { pos: t('memory.card', { i: i + 1, n: deck.length }) })}">
            <span class="memory-card-inner">
                <span class="memory-card-front"><i class="fas fa-question" aria-hidden="true"></i></span>
                <span class="memory-card-back"><img src="${card.image}" alt=""></span>
            </span>
        </button>
    `).join('');

    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback';
    feedback.innerHTML = '';

    container.dataset.memoryMatched = '0';
    const isReshuffle = grid.children.length > 0;

    if (isReshuffle) {
        // Visible feedback on reshuffle: short fade and icon spin.
        container.dataset.memoryBusy = '1';
        container.classList.add('shuffling');
        setTimeout(() => {
            grid.innerHTML = deckHTML;
            container.classList.remove('shuffling');
            container.dataset.memoryBusy = '0';
            updateMemoryProgress(container);
        }, 280);
    } else {
        grid.innerHTML = deckHTML;
        container.dataset.memoryBusy = '0';
        updateMemoryProgress(container);
    }
}

function updateMemoryProgress(container) {
    const matched = parseInt(container.dataset.memoryMatched || '0', 10);
    const total = container.querySelectorAll('.memory-card').length / 2;
    const el = container.querySelector('.memory-progress');
    if (el) el.textContent = t('memory.pairs', { n: matched, total });
}

function handleMemoryCardClick(card) {
    const container = card.closest('.memory-container');
    if (!container) return;
    if (container.dataset.memoryBusy === '1') return;
    if (card.classList.contains('matched') || card.classList.contains('flipped')) return;

    // On the third card, flip the previous non-matching pair back.
    const pending = container.querySelectorAll('.memory-card.flipped:not(.matched)');
    if (pending.length >= 2) {
        pending.forEach(c => c.classList.remove('flipped'));
    }

    card.classList.add('flipped');
    const flipped = container.querySelectorAll('.memory-card.flipped:not(.matched)');

    if (flipped.length === 2) {
        const [a, b] = flipped;
        if (a.dataset.pairId === b.dataset.pairId) {
            // Short lock so the second card's flip finishes before the match pulse starts.
            container.dataset.memoryBusy = '1';
            setTimeout(() => {
                a.classList.add('matched');
                b.classList.add('matched');
                const matched = parseInt(container.dataset.memoryMatched || '0', 10) + 1;
                container.dataset.memoryMatched = String(matched);
                container.dataset.memoryBusy = '0';
                updateMemoryProgress(container);
                const total = container.querySelectorAll('.memory-card').length / 2;
                if (matched === total) completeMemoryGame(container);
            }, 350);
        }
        // No match: cards stay open until the player clicks a third card.
    }
}

function completeMemoryGame(container) {
    const quizId = container.dataset.quizId;
    const feedback = container.querySelector('.quiz-feedback');
    feedback.className = 'quiz-feedback show success';
    feedback.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t('memory.done')}`;
    if (addCompletedQuizId(quizId)) showBadgeNotification();
}

document.addEventListener('change', (e) => {
    const input = e.target.closest('.quiz-option input');
    if (!input) return;
    const container = input.closest('.quiz-container');
    if (container) updateQuizOptionStates(container);
});

document.addEventListener('click', (e) => {
    const submitBtn = e.target.closest('.quiz-submit-btn');
    if (submitBtn) {
        evaluateQuiz(submitBtn.closest('.quiz-container'));
        return;
    }
    const resetBtn = e.target.closest('.quiz-reset-btn, .memory-reset-btn');
    if (resetBtn) {
        const container = resetBtn.closest('.quiz-container');
        if (container) resetQuiz(container);
        return;
    }
    const hintBtn = e.target.closest('.wordsearch-hint-btn');
    if (hintBtn) {
        const container = hintBtn.closest('.wordsearch-container');
        if (container) showWordsearchHint(container);
        return;
    }
    const sortArrow = e.target.closest('.sort-arrow-btn');
    if (sortArrow) {
        e.preventDefault();
        e.stopPropagation();
        if (sortArrow.disabled) return;
        const item = sortArrow.closest('.sort-item');
        const container = sortArrow.closest('.sort-container');
        if (item && container && !item.classList.contains('locked')) {
            moveSortItem(item, sortArrow.dataset.direction);
        }
        return;
    }
    const memoryCard = e.target.closest('.memory-card');
    if (memoryCard) {
        handleMemoryCardClick(memoryCard);
        return;
    }
    const hotspotOverlay = e.target.closest('.hotspot-overlay');
    if (hotspotOverlay) {
        handleHotspotClick(hotspotOverlay, e);
    }
});

document.addEventListener('shown.bs.modal', (e) => {
    const container = e.target.querySelector('.quiz-container');
    if (container) resetQuiz(container);
});

const filterStyleEl = document.createElement('style');
document.head.appendChild(filterStyleEl);
const filterState = {};

function updateFilterStyles() {
    // Without visible quizzes the badge icon is pointless too.
    const badgeBtn = document.getElementById('toolboxBadgesBtn');
    if (badgeBtn) badgeBtn.hidden = filterState['Studierende_mit_Fragen'] === false;

    filters.forEach(({ id }) => {
        const key = Array.isArray(id) ? id.join(',') : id;
        const visible = filterState[key];
        const ids = Array.isArray(id) ? id : [id];

        ids.forEach(singleId => {
            document.querySelectorAll(`#lottieMap svg #${singleId} > *`)
                .forEach(el => {
                    el.style.display = visible ? '' : 'none';
                });
        });
    });

    layoutMapLegends();
}

// Layer legends (accessibility, WC, elevators, info, …) live in their layer and toggle with it.
// Visible legends pack without gaps (masonry): in data-legend-row/-order each goes into the shortest column; column count = distinct data-legend-x values in the SVG.
const LEGEND_GAP = 6;

function layoutMapLegends() {
    const legends = Array.from(document.querySelectorAll('#lottieMap svg .legende'));
    if (!legends.length) return;
    const num = (el, key) => Number(el.dataset[key]);

    const left = Math.min(...legends.map(l => num(l, 'legendX')));
    const top = Math.min(...legends.map(l => num(l, 'legendY')));
    const colWidth = Math.max(...legends.map(l => num(l, 'legendW'))) + LEGEND_GAP;
    const colCount = new Set(legends.map(l => num(l, 'legendX'))).size;
    const colHeights = new Array(colCount).fill(top);

    legends
        .filter(l => getComputedStyle(l).display !== 'none')
        .sort((a, b) => num(a, 'legendRow') - num(b, 'legendRow') || num(a, 'legendOrder') - num(b, 'legendOrder'))
        .forEach(legend => {
            const col = colHeights.indexOf(Math.min(...colHeights));
            const dx = left + col * colWidth - num(legend, 'legendX');
            const dy = colHeights[col] - num(legend, 'legendY');
            legend.setAttribute('transform', `translate(${dx} ${dy})`);
            colHeights[col] += num(legend, 'legendH') + LEGEND_GAP;
        });
}

// Initialize the filter UI.
function initFilters() {
    const container = document.getElementById('filterOptions');
    if (!container) return;

    // Remove existing filters to avoid duplicates.
    container.innerHTML = '';

    // Load saved settings.
    const savedSettings = localStorage.getItem('filter_settings_v3');
    const savedState = savedSettings ? JSON.parse(savedSettings) : {};

    filters.forEach((filter, index) => {
        const key = Array.isArray(filter.id) ? filter.id.join(',') : filter.id;

        // Restore the state or use the default.
        if (savedState.hasOwnProperty(key)) {
            filterState[key] = savedState[key];
        } else {
            filterState[key] = filter.defaultVisible;
        }

        const filterId = `filter-${index}`;
        const isChecked = filterState[key];

        const html = `
      <label class="filter-card ${isChecked ? 'active' : ''}" for="${filterId}">
        <div class="filter-card-content">
          <img src="${filter.icon}" alt="" class="filter-icon">
          <span class="filter-label-text">${filter.label}</span>
        </div>
        <div class="filter-toggle">
          <input type="checkbox" id="${filterId}" ${isChecked ? 'checked' : ''}>
          <span class="toggle-slider"></span>
        </div>
      </label>
    `;

        const div = document.createElement('div');
        div.innerHTML = html;
        const labelEl = div.firstElementChild;
        const checkbox = labelEl.querySelector('input');

        checkbox.addEventListener('change', (e) => {
            const checked = e.target.checked;
            filterState[key] = checked;

            if (checked) {
                labelEl.classList.add('active');
            } else {
                labelEl.classList.remove('active');
            }

            // Save settings.
            localStorage.setItem('filter_settings_v3', JSON.stringify(filterState));

            updateFilterStyles();
            updateToggleAllButton();
        });

        container.appendChild(div);
    });

    // "Show all" button logic.
    let toggleAllBtn = document.getElementById('toggleAllBtn');
    if (toggleAllBtn) {
        // Clear event listeners by cloning.
        const newBtn = toggleAllBtn.cloneNode(true);
        toggleAllBtn.parentNode.replaceChild(newBtn, toggleAllBtn);
        toggleAllBtn = newBtn;

        toggleAllBtn.addEventListener('click', () => {
            // Check whether everything is currently visible.
            const allVisible = filters.every(filter => {
                const key = Array.isArray(filter.id) ? filter.id.join(',') : filter.id;
                return filterState[key] === true;
            });

            const newState = !allVisible;

            filters.forEach(filter => {
                const key = Array.isArray(filter.id) ? filter.id.join(',') : filter.id;
                filterState[key] = newState;
            });

            // Update the UI.
            document.querySelectorAll('#filterOptions input').forEach(cb => {
                cb.checked = newState;
                if (newState) {
                    cb.closest('.filter-card').classList.add('active');
                } else {
                    cb.closest('.filter-card').classList.remove('active');
                }
            });

            localStorage.setItem('filter_settings_v3', JSON.stringify(filterState));
            updateFilterStyles();
            updateToggleAllButton();
        });
    }

    updateToggleAllButton();
    updateFilterStyles();
}

function updateToggleAllButton() {
    const toggleAllBtn = document.getElementById('toggleAllBtn');
    if (!toggleAllBtn) return;

    // Check whether everything is visible.
    const allVisible = filters.every(filter => {
        const key = Array.isArray(filter.id) ? filter.id.join(',') : filter.id;
        return filterState[key] === true;
    });

    if (allVisible) {
        toggleAllBtn.classList.add('active');
        toggleAllBtn.innerHTML = `<i class="fas fa-eye-slash me-2" aria-hidden="true"></i>${t('filters.hideAll')}`;
    } else {
        toggleAllBtn.classList.remove('active');
        toggleAllBtn.innerHTML = `<i class="fas fa-eye me-2" aria-hidden="true"></i>${t('filters.showAll')}`;
    }
}

let interactionType = null;

function buildSelector({ exactMatches = [] }) {
    // Select exactly these ids.
    return exactMatches
        .map(id => `#${id}`)
        .join(', ');
}//buildSelector

const clickableSelectorMap = buildSelector(CLICKABLE_Geb_CONFIG.lottieMap);

const styleTag = document.createElement('style');

styleTag.textContent = `
/* Map layer: only our include selectors, minus classes from excludeMatches */
#lottieMap svg ${clickableSelectorMap},
#lottieMap svg ${clickableSelectorMap} * {
  pointer-events: all !important; cursor: pointer !important;
}
/* Building labels sit above the shapes, pass events through */
#lottieMap svg g#Gebaeudebezeichnung,
#lottieMap svg g#Gebaeudebezeichnung * {
  pointer-events: none !important;
}
  `;
document.head.appendChild(styleTag);

// JSON loader; avoids double caching.
let jsonCache = new Map(); // Global cache

async function loadJSON(url) {
    // 1. Check the cache first.
    if (jsonCache.has(url)) {
        return jsonCache.get(url);
    }

    // 2. Fetch with cache-friendly headers.
    const r = await fetch(url, {
        cache: 'force-cache', // Use the browser cache
        headers: {
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=3600' // 1 hour cache
        }
    });

    if (!r.ok) throw new Error(r.status);

    const data = await r.json();
    jsonCache.set(url, data);

    return data;
}

/**
 * Rebuilds the offcanvas HTML and writes it into #buildingInfoContent.
 * @param {Object} b – building object with title, images?, description?, featureSections?, openingHours?
 */
function renderBuildingOffcanvas(b) {
    let html = "";


    // 2) Image(s): single image or carousel.
    if (b.images?.length === 1) {
        html += `
      <div class="mb-3">
        <img src="${b.images[0]}" alt="${b.title}" class="d-block w-100 mb-0 building-carousel-img">
      </div>`;
    } else if (b.images?.length > 1) {
        html += `
     <div id="carouselBuilding" class="carousel slide carousel-fade mb-3" data-bs-ride="carousel">
        <div class="carousel-indicators">
          ${b.images.map((_, i) => `
            <button type="button" data-bs-target="#carouselBuilding" data-bs-slide-to="${i}"${i === 0 ? ' class="active" aria-current="true"' : ''}
                    aria-label="${t('carousel.goto', { i: i + 1, n: b.images.length })}"></button>`).join("")}
        </div>
        <div class="carousel-inner">
          ${b.images.map((src, i) => `
            <div class="carousel-item${i === 0 ? ' active' : ''}">
              <img src="${src}" alt="${t('building.imageAlt', { title: b.title, i: i + 1, n: b.images.length })}"
                   class="d-block w-100 mb-0 building-carousel-img">
            </div>`).join("")}
        </div>
        <button class="carousel-control-prev" type="button"
                data-bs-target="#carouselBuilding" data-bs-slide="prev">
          <span class="carousel-control-prev-icon" aria-hidden="true"></span>
          <span class="visually-hidden">${t('carousel.prev')}</span>
        </button>
        <button class="carousel-control-next" type="button"
                data-bs-target="#carouselBuilding" data-bs-slide="next">
          <span class="carousel-control-next-icon" aria-hidden="true"></span>
          <span class="visually-hidden">${t('carousel.next')}</span>
        </button>
      </div>`;
    }

    // 3) Description and icon side by side (3/4 text, 1/4 icon).
    if (b.description || b.icon) {
        html += `
      <div class="content-group mb-3 px-sm-0 px-md-4">
        <div class="row align-items-center">
          <div class="col-12 col-md-9 pr-md-0 order-0 order-md-0">
            ${b.description ? `<p class="mb-0-important">${b.description}</p>` : ""}
          </div>
          <div class="col-6 offset-3 col-md-3 offset-md-0 text-center px-0 order-1 order-md-1 mt-3 mt-md-0">
            ${b.icon
                ? `<img 
  src="${b.icon}" 
  alt=""
  class="building-icon-img" style="height:${b.iconHeight || 'auto'};">
`
                : ""}
          </div>

        </div>
      </div>`;
    }

    // 4) Feature sections
    if (b.featureSections) {
        b.featureSections.forEach(sec => {
            html += `
        <div class="content-group mb-3 px-sm-0 px-md-4">
          <p class="fw-bold mb-1 building-section-title" style="color:${sec.color || '#000'}">
            ${sec.heading}
          </p>
          <ul class="mb-0 ps-3">
            ${sec.items.map(item => `<li>${item}</li>`).join("")}
          </ul>
        </div>`;
        });
    }

    // 5) Opening hours
    if (b.openingHours?.slots) {
        html += `
      <div class="content-group mb-3 px-sm-0 px-md-4 building-hours-container"
           style="background:${b.openingHours.bgColor};">
        <p class="fw-bold mb-2 building-hours-title" style="color:${b.openingHours.color || '#000'}">
          ${b.openingHours.label}
        </p>
        ${b.openingHours.slots.map(s =>
            `<div>
     <strong>${s.label}</strong>
     <p class="d-inline m-0">${s.time}</p>
   </div>`
        ).join("")}

      </div>`;
    }

    // 6) Link button at the bottom
    if (b.link) {
        html += `
      <div class="content-group mb-3 px-sm-0 px-md-4">
        ${b.link.title ? `<p class="fw-bold mb-2 text-dark">${b.link.title}</p>` : ''}
        <a href="${b.link.url}" target="_blank" class="erkundungstour-btn">
          <p>${b.link.text}</p>
        </a>
      </div>`;
    }

    // 7) Render
    document.getElementById('buildingInfoContent').innerHTML = html;
}

/**
 * Looks up the building in campusBuildings, renders it via renderBuildingOffcanvas() and shows the offcanvas.
 * @param {string} id – SVG id of the clicked building
 * @param {Object} [opts]
 * @param {boolean} [opts.fromLegend] – opened from the legend: show the back button and "show on map" (see legend.js)
 */
function openBuildingInfo(id, opts = {}) {
    const b = campusBuildings.find(x => x.id === id);
    if (!b) return;

    const panel = document.getElementById('buildingInfoOffcanvas');
    const header = document.getElementById('buildingInfoLabel');
    header.textContent = b.title;
    header.style.color = b.titleColor || '';

    renderBuildingOffcanvas(b);
    window.campusLegend?.onDetailShown(id, opts.fromLegend);

    // Panel already open (switch from the legend): no shown event, so start the carousel here.
    if (panel.classList.contains('show')) {
        startBuildingCarousel();
        if (typeof enhanceBuildingCarousel === 'function') window.setTimeout(enhanceBuildingCarousel, 0);
    } else {
        bootstrap.Offcanvas.getOrCreateInstance(panel).show();
    }
}

function startBuildingCarousel() {
    const el = document.getElementById('carouselBuilding');
    if (!el) return;

    const inst = bootstrap.Carousel.getOrCreateInstance(el, {
        interval: 3000,
        pause: false,
        wrap: true,
        touch: true
    });
    inst.cycle();

    // Set all transition durations to 0 for the next slide change.
    const disableOnce = () => {
        // Active immediately, before the Bootstrap handler.
        el.classList.add('no-anim');
        const onSlid = () => {
            el.classList.remove('no-anim');   // Auto slide fades again
            el.removeEventListener('slid.bs.carousel', onSlid);
        };
        el.addEventListener('slid.bs.carousel', onSlid);
    };

    const prev = el.querySelector('.carousel-control-prev');
    const next = el.querySelector('.carousel-control-next');

    prev?.addEventListener('pointerdown', disableOnce);
    next?.addEventListener('pointerdown', disableOnce);

    // Optional: keyboard
    el.addEventListener('keydown', e => {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') disableOnce();
    });
}

/**
 * Opens a Bootstrap modal and lazy-loads its iframe.
 * @param {string} id          overlay id
 * @param {string} [modalId]   modal id; defaults to `id + '_modal'`
 */
function openTarget(id, modalId) {
    const mId = modalId && modalId.trim() ? modalId : `${id}_modal`;
    const modalElement = document.getElementById(mId);
    if (!modalElement) return;
    bootstrap.Modal.getOrCreateInstance(modalElement).show();
}
//openTarget


function runIntroZoom(svg, orig, durationMs = 3000) {
    // Mobile detection
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
        window.innerWidth <= 768;

    // Mobile uses its own duration.
    const actualDuration = isMobile ? 3000 : durationMs;

    let cancelled = false;
    const start = performance.now();
    (function anim(now) {
        // On skip the SVG stays the same; without cancelling, the running zoom would overwrite the final state.
        if (cancelled) return;
        const t = Math.min(1, (now - start) / actualDuration);
        const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

        let z, centerX, centerY;

        if (isMobile) {
            // Mobile: zoom from 0.5x to 2.8x.
            z = 0.5 + 2.3 * ease;
            // Mobile centers slightly right and up.
            centerX = orig.width * 0.62; // 62% of the width
            centerY = orig.height * 0.42; // 42% of the height
        } else {
            // Desktop: zoom from 0.5x to 1.0x into the center.
            z = 0.5 + 0.5 * ease;
            centerX = orig.width / 2;
            centerY = orig.height / 2;
        }

        const vb = svg.viewBox.baseVal;
        const w = orig.width / z;
        const h = orig.height / z;
        vb.width = w;
        vb.height = h;
        vb.x = centerX - w / 2;
        vb.y = centerY - h / 2;

        if (t < 1) requestAnimationFrame(anim);
        else {
            // After the intro zoom, correct only extreme values.
            setTimeout(() => {
                const vb = svg.viewBox.baseVal;
                const currentZoom = orig.width / vb.width;
                if (currentZoom > 4.0) {
                    // Clamp to maxZoom only for extreme zoom (>4x).
                    const newW = orig.width / 3.5;
                    const newH = orig.height / 3.5;
                    vb.width = newW;
                    vb.height = newH;
                    // Keep the center.
                    const centerX = vb.x + vb.width / 2;
                    const centerY = vb.y + vb.height / 2;
                    vb.x = centerX - newW / 2;
                    vb.y = centerY - newH / 2;
                }
            }, 100);
        }
    })(start);

    return { cancel: () => { cancelled = true; } };
}

const clickGroups = [
    { containerId: 'Frage', prefix: 'Frage', modalSuffix: '_modal', handler: openTarget },
    ...Array.from({ length: 10 }, (_, i) => ({
        containerId: `Frage-${i + 1}`,
        prefix: 'Frage',
        modalSuffix: '_modal',
        handler: openTarget
    })),
    {
        containerId: 'Buttons',
        prefix: '',
        modalSuffix: '_modal',
        handler: (id) => {
            const urls = {
                Button_Innenstadt: 'https://www.luebeck-tourismus.de/altstadt',
                Button_Studium: 'https://www.th-luebeck.de/studium/studienangebot/studiengaenge/',
                Button_Hochschulsport: 'https://www.hochschulsport-luebeck.de/',
                Button_Speiseplan: 'https://studentenwerk.sh/de/mensen-in-luebeck?ort=3&mensa=8#mensaplan',
                Button_FabLab: 'https://www.fablab-luebeck.de/de',
                Button_Erkundungstour: 'https://www.th-luebeck.de/hochschule/aktuelles/neuigkeiten/beitrag/2023-03-13-premiere-neuer-film-zeigt-th-luebeck-als-transferhochschule/'
            };
            if (urls[id]) window.open(urls[id], '_blank');
        }
    },
    { containerId: 'Kaffee', prefix: '', modalSuffix: '', handler: (id) => openBuildingInfo(id) },
    { containerId: 'Logo', prefix: '', modalSuffix: '', handler: () => window.open('https://www.th-luebeck.de/', '_blank') }
];

// Zoom & Pan Setup
function setupZoomPan() {
    const container = document.getElementById('mapContainer');
    const svgs = [
        document.querySelector('#lottieMap svg'),
    ].filter(Boolean);
    const orig = svgs.map(svg => {
        // Use the real map size (1920x1080) as reference.
        return { width: 1920, height: 1080 };
    });
    const minZoom = 1, maxZoom = 3.5;
    function clamp(vb, oW, oH) {
        vb.x = Math.max(-vb.width / 2, Math.min(oW - vb.width / 2, vb.x));
        vb.y = Math.max(-vb.height / 2, Math.min(oH - vb.height / 2, vb.y));
    }
    function doZoom(scaleAmt, cx, cy) {
        svgs.forEach((svg, i) => {
            const vb = svg.viewBox.baseVal;
            const { width: oW, height: oH } = orig[i];
            const curr = oW / vb.width;
            let nz = curr * scaleAmt;

            // Allow zoom from 1.0x to 3.5x on all devices.
            nz = Math.min(3.5, Math.max(1.0, nz));

            const newW = oW / nz, newH = oH / nz;
            const pt = svg.createSVGPoint(); pt.x = cx; pt.y = cy;
            const c = pt.matrixTransform(svg.getScreenCTM().inverse());
            vb.x = c.x - (c.x - vb.x) * (newW / vb.width);
            vb.y = c.y - (c.y - vb.y) * (newH / vb.height);
            vb.width = newW; vb.height = newH;
            clamp(vb, oW, oH);
        });
    }

    let lastPtr = null;
    container.addEventListener('pointerdown', e => {
        if (e.target.closest && e.target.closest('.map-controls')) return;
        if (e.pointerType === 'mouse' || e.pointerType === 'pen') {
            e.preventDefault();
            lastPtr = { x: e.clientX, y: e.clientY };
            interactionType = 'tap';
            container.classList.add('grabbing');
        }
    }, { passive: false });
    container.addEventListener('pointermove', e => {
        if ((e.pointerType === 'mouse' || e.pointerType === 'pen') && lastPtr) {
            e.preventDefault();
            const prev = lastPtr, curr = { x: e.clientX, y: e.clientY };
            lastPtr = curr;
            if (Math.hypot(curr.x - prev.x, curr.y - prev.y) > 5) interactionType = 'pan';
            svgs.forEach((svg, i) => {
                const vb = svg.viewBox.baseVal;
                const p1 = svg.createSVGPoint(); p1.x = prev.x; p1.y = prev.y;
                const s1 = p1.matrixTransform(svg.getScreenCTM().inverse());
                const p2 = svg.createSVGPoint(); p2.x = curr.x; p2.y = curr.y;
                const s2 = p2.matrixTransform(svg.getScreenCTM().inverse());
                vb.x -= (s2.x - s1.x);
                vb.y -= (s2.y - s1.y);
                clamp(vb, orig[i].width, orig[i].height);
            });
        }
    }, { passive: false });
    ['pointerup', 'pointercancel'].forEach(evt =>
        container.addEventListener(evt, e => {
            if (e.pointerType === 'mouse' || e.pointerType === 'pen') {
                lastPtr = null;
                container.classList.remove('grabbing');
            }
        })
    );
    const ts = { mode: null, startTouch: null, startDist: 0, startVBs: null };
    container.addEventListener('touchstart', e => {
        if (e.target.closest && e.target.closest('.map-controls')) return;
        e.preventDefault();
        const t = e.touches;
        interactionType = 'tap';
        if (t.length === 1) {
            ts.mode = 'pan';
            ts.startTouch = { x: t[0].clientX, y: t[0].clientY };
        } else if (t.length === 2) {
            ts.mode = 'pinch';
            interactionType = 'pinch';
            ts.startDist = Math.hypot(
                t[0].clientX - t[1].clientX,
                t[0].clientY - t[1].clientY
            );
            ts.startVBs = svgs.map(svg => ({ ...svg.viewBox.baseVal }));
        }
    }, { passive: false });
    container.addEventListener('touchmove', e => {
        e.preventDefault();
        const t = e.touches;
        if (ts.mode === 'pan' && t.length === 1) {
            const prev = ts.startTouch, curr = { x: t[0].clientX, y: t[0].clientY };
            if (Math.hypot(curr.x - prev.x, curr.y - prev.y) > 5) interactionType = 'pan';
            svgs.forEach((svg, i) => {
                const vb = svg.viewBox.baseVal;
                const p1 = svg.createSVGPoint(); p1.x = prev.x; p1.y = prev.y;
                const s1 = p1.matrixTransform(svg.getScreenCTM().inverse());
                const p2 = svg.createSVGPoint(); p2.x = curr.x; p2.y = curr.y;
                const s2 = p2.matrixTransform(svg.getScreenCTM().inverse());
                vb.x -= (s2.x - s1.x);
                vb.y -= (s2.y - s1.y);
                clamp(vb, orig[i].width, orig[i].height);
            });
            ts.startTouch = curr;
        } else if (ts.mode === 'pinch' && t.length === 2) {
            const dist = Math.hypot(
                t[0].clientX - t[1].clientX,
                t[0].clientY - t[1].clientY
            );
            const scaleAmt = dist / ts.startDist;
            ts.startDist = dist;
            const rect = container.getBoundingClientRect();
            const cx = (t[0].clientX + t[1].clientX) / 2 - rect.left;
            const cy = (t[0].clientY + t[1].clientY) / 2 - rect.top;
            doZoom(scaleAmt, cx, cy);
            interactionType = 'pinch';
        }
    }, { passive: false });
    container.addEventListener('wheel', e => {
        e.preventDefault();
        doZoom(1 - e.deltaY * 0.002, e.offsetX, e.offsetY);
        interactionType = 'pan';
    }, { passive: false }); //wheel



    container.addEventListener('pointerup', e => {
        if (!['mouse', 'touch', 'pen'].includes(e.pointerType) || interactionType !== 'tap') {
            return;
        }
        // The zoom buttons sit in the map container but are not map elements.
        if (e.target.closest && e.target.closest('.map-controls')) return;

        activateMapTarget(e.target, e);
        interactionType = null;
    });

    // Expose the zoom logic: the buttons in a11y.js need it as an alternative to wheel and pinch (WCAG 2.5.1 pointer gestures).
    window.mapZoomControls = {
        zoomIn: () => doZoom(1.3, window.innerWidth / 2, window.innerHeight / 2),
        zoomOut: () => doZoom(1 / 1.3, window.innerWidth / 2, window.innerHeight / 2),
        reset: () => {
            svgs.forEach((svg, i) => {
                const vb = svg.viewBox.baseVal;
                vb.x = 0;
                vb.y = 0;
                vb.width = orig[i].width;
                vb.height = orig[i].height;
            });
        },
        // Pans until the element is visible (keyboard focus on a zoomed-in map); nothing to do when not zoomed.
        panToElement: (el) => {
            const svg = svgs[0];
            if (!svg || !el) return;
            const vb = svg.viewBox.baseVal;
            if (vb.width >= orig[0].width) return;
            const box = el.getBoundingClientRect();
            const view = container.getBoundingClientRect();
            const rand = 40;
            if (box.left >= view.left + rand && box.right <= view.right - rand &&
                box.top >= view.top + rand && box.bottom <= view.bottom - rand) return;
            const scale = svg.getScreenCTM().a;
            const dx = (box.left + box.width / 2) - (view.left + view.width / 2);
            const dy = (box.top + box.height / 2) - (view.top + view.height / 2);
            vb.x += dx / scale;
            vb.y += dy / scale;
            clamp(vb, orig[0].width, orig[0].height);
        },
        // Flies to the element (legend "show on map"); region is the free part of the screen (without header/panel) where the element is centered. Only zooms in, never out.
        flyToElement: (el, { region, zoom = 2, animate = true, duration = 700 } = {}) => {
            const svg = svgs[0];
            if (!svg || !el) return Promise.resolve();
            const box = el.getBoundingClientRect();
            if (!box.width && !box.height) return Promise.resolve();
            const area = region || container.getBoundingClientRect();
            const vb = svg.viewBox.baseVal;
            const from = { x: vb.x, y: vb.y, width: vb.width, height: vb.height };

            const toSvg = (x, y, ctm) => {
                const p = svg.createSVGPoint(); p.x = x; p.y = y;
                return p.matrixTransform(ctm.inverse());
            };
            const c = toSvg(box.left + box.width / 2, box.top + box.height / 2, svg.getScreenCTM());

            // Compute the target viewport: size first, then shift so the element is centered in the free area.
            const nz = Math.min(maxZoom, Math.max(minZoom, zoom, orig[0].width / vb.width));
            vb.width = orig[0].width / nz;
            vb.height = orig[0].height / nz;
            vb.x = c.x - vb.width / 2;
            vb.y = c.y - vb.height / 2;
            const ctm = svg.getScreenCTM();
            const p = svg.createSVGPoint(); p.x = c.x; p.y = c.y;
            const s = p.matrixTransform(ctm);
            vb.x -= (area.left + area.width / 2 - s.x) / ctm.a;
            vb.y -= (area.top + area.height / 2 - s.y) / ctm.d;
            // Near the map edge, do not pan past it (would leave an empty white strip).
            const edge = svg.getScreenCTM();
            const mapL = edge.e, mapR = edge.e + orig[0].width * edge.a;
            const mapT = edge.f, mapB = edge.f + orig[0].height * edge.d;
            const areaR = area.left + area.width, areaB = area.top + area.height;
            if (mapR - mapL >= area.width) {
                if (mapL > area.left) vb.x += (mapL - area.left) / edge.a;
                else if (mapR < areaR) vb.x -= (areaR - mapR) / edge.a;
            }
            if (mapB - mapT >= area.height) {
                if (mapT > area.top) vb.y += (mapT - area.top) / edge.d;
                else if (mapB < areaB) vb.y -= (areaB - mapB) / edge.d;
            }
            clamp(vb, orig[0].width, orig[0].height);
            const to = { x: vb.x, y: vb.y, width: vb.width, height: vb.height };

            if (!animate) return Promise.resolve();
            Object.assign(vb, from);
            return new Promise(resolve => {
                const start = performance.now();
                (function step(now) {
                    const k = Math.min(1, (now - start) / duration);
                    const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
                    vb.x = from.x + (to.x - from.x) * e;
                    vb.y = from.y + (to.y - from.y) * e;
                    vb.width = from.width + (to.width - from.width) * e;
                    vb.height = from.height + (to.height - from.height) * e;
                    if (k < 1) requestAnimationFrame(step);
                    else resolve();
                })(start);
            });
        },
        zoomText: () => {
            const svg = svgs[0];
            if (!svg) return '';
            const stufe = orig[0].width / svg.viewBox.baseVal.width;
            return `Zoomstufe ${Math.round(stufe * 100)} Prozent`;
        }
    };
}//setupZoomPan

/**
 * Runs the action that belongs to a map element.
 * Mouse/touch (pointerup) and keyboard (Enter/Space in a11y.js) both call this so they never diverge.
 * @param {Element} target - the tapped or focused SVG element
 * @param {Event}  [evt]   - the triggering event, if any
 */
function activateMapTarget(target, evt) {
    if (!target) return;

    // 1) Special case logo (no child loop).
    const logoEl = document.getElementById('Logo');
    if (logoEl && logoEl.contains(target)) {
        window.open('https://www.th-luebeck.de/', '_blank');
        return;
    }

    // 2) All other clickGroups as before.
    for (const { containerId, prefix, modalSuffix, handler } of clickGroups) {
        if (containerId === 'Logo') continue; // Logo handled above

        const containerEl = document.getElementById(containerId);
        if (!containerEl) continue;

        if (containerEl.contains(target)) {
            if (evt) evt.stopPropagation();

            // Derive the id from containerId.
            let itemId;
            if (prefix) {
                // For Frage-X: "Frage-5" → "Frage5"
                itemId = containerId.replace('-', '');
                const modalId = `${itemId}${modalSuffix}`;
                handler(itemId, modalId);
            } else {
                // Other containers: walk all direct children.
                for (const child of containerEl.children) {
                    if (child.contains(target)) {
                        if (child.id) {
                            const modalId = `${child.id}${modalSuffix}`;
                            handler(child.id, modalId);
                            break;
                        }
                    }
                }
            }
            return;
        }
    }

    // 3) Building offcanvas last.
    const elGeb = target.closest(clickableSelectorMap);
    if (elGeb) {
        const gebId = elGeb.id;
        if (campusBuildings.some(b => b.id === gebId)) {
            openBuildingInfo(gebId);
        }
    }
}

// Map aspect ratio: on laptop screens slightly wider than 16:9 the map fills the full width (no white side bars) and is cropped only at the top, under the header, so the logo at the bottom stays intact.
// Large screens and narrower windows still show the whole map with margins.
const MAP_FILL_MAX_WIDTH = 1800;
const MAP_FILL_MAX_RATIO = 2.1;

function mapAspectRatio() {
    const box = document.getElementById('mapContainer');
    if (!box || !box.clientHeight) return 'xMidYMid meet';
    const ratio = box.clientWidth / box.clientHeight;
    const fill = box.clientWidth < MAP_FILL_MAX_WIDTH
        && ratio > 1920 / 1080 && ratio <= MAP_FILL_MAX_RATIO;
    return fill ? 'xMidYMax slice' : 'xMidYMid meet';
}

function applyMapAspectRatio() {
    document.querySelector('#lottieMap svg')?.setAttribute('preserveAspectRatio', mapAspectRatio());
}

window.addEventListener('resize', applyMapAspectRatio);

// ============================================================
// Load the map and play the intro
// ============================================================
//
// The intro runs directly on campus_map_v2.svg (formerly a separate Lottie animation, then a switch to the SVG), so it always shows the current map with no jump at the end.

const INTRO_DURATION_MS = 5000;
// Timings come from the former Lottie intro (25 fps = 40 ms).
const introFrame = n => n * 40;

// Order in which the areas appear (frame in the old intro).
const INTRO_BEREICHE = {
    Bereich_E: 18, Bereich_A: 21, Bereich_B: 38, Bereich_F: 48,
    Bereich_G: 61, Bereich_D: 76, Interimsbau: 76, Bereich_C: 78, Bereich_MFC: 90
};

// Layers not animated individually fade in together at the end (streets, labels, buttons, quiz figures, legends, …); new SVG layers land here automatically.
const INTRO_EIGENE_ANIMATION = ['Hg', 'Logo', 'Bereiche', 'Gebaeude', 'Kaffee', 'Bushaltestellen', 'Fahrradstationen'];

/**
 * Plays the intro on the rendered map.
 * @returns {{finish: Function}} – finish() jumps straight to the end
 */
function runMapIntro(svg) {
    const animationen = [];

    // Groups with their own transform attribute (e.g. scaled icons) must not get a CSS transform, which would replace the attribute; an inner wrapper is animated instead.
    const ziel = el => {
        if (!el.hasAttribute('transform')) return el;
        const innen = document.createElementNS(svg.namespaceURI, 'g');
        // Only groups can hold child <g>; e.g. <text> gets a wrapper around it instead (otherwise its content is not drawn).
        if (el.tagName.toLowerCase() !== 'g') {
            el.replaceWith(innen);
            innen.appendChild(el);
            return innen;
        }
        while (el.firstChild) innen.appendChild(el.firstChild);
        el.appendChild(innen);
        return innen;
    };
    const animiere = (el, keyframes, delay, duration, easing = 'ease-out', origin = '50% 100%') => {
        if (!el || !el.animate) return;
        el.style.transformBox = 'fill-box';
        el.style.transformOrigin = origin;
        // fill 'backwards': invisible before start, normal state afterwards (no inline transform remains).
        animationen.push(el.animate(keyframes, { delay, duration, easing, fill: 'backwards' }));
    };
    const kinder = id => Array.from(svg.querySelectorAll(`g#${id} > *`));

    // 1) Areas appear one after another, their letters pop briefly.
    const bereiche = [];
    Object.entries(INTRO_BEREICHE).forEach(([id, bild]) => {
        const g = svg.querySelector(`g#${id}`);
        if (!g) return;
        const flaeche = g.querySelector(`g#${id}-2`) || g;
        bereiche.push({ start: introFrame(bild), box: flaeche.getBBox() });
        animiere(g, [{ opacity: 0 }, { opacity: 1 }], introFrame(bild), 120, 'linear');
        Array.from(g.children).filter(c => c !== flaeche).forEach(buchstabe => {
            animiere(buchstabe,
                [{ transform: 'scale(1)' }, { transform: 'scale(1.5)' }, { transform: 'scale(1)' }],
                introFrame(bild + 1), 320, 'ease-in-out', '50% 50%');
        });
    });

    // 2) Buildings grow up one by one within their area; the area is derived from position, so new buildings need no maintenance.
    const bereichVon = el => {
        const b = el.getBBox();
        const x = b.x + b.width / 2, y = b.y + b.height / 2;
        const drin = bereiche
            .filter(({ box }) => x >= box.x && x <= box.x + box.width && y >= box.y && y <= box.y + box.height)
            .sort((p, q) => p.box.width * p.box.height - q.box.width * q.box.height);
        if (drin.length) return drin[0];
        // Outside all areas: take the nearest.
        return bereiche.slice().sort((p, q) => {
            const d = ({ box }) => Math.hypot(box.x + box.width / 2 - x, box.y + box.height / 2 - y);
            return d(p) - d(q);
        })[0];
    };
    // Other items in the areas layer (e.g. the "Campuswiese" label) appear with the area they lie in.
    if (bereiche.length) {
        kinder('Bereiche')
            .filter(el => !(el.id in INTRO_BEREICHE))
            .forEach(el => animiere(el, [{ opacity: 0 }, { opacity: 1 }], bereichVon(el).start, 120, 'linear'));
    }

    const proBereich = new Map();
    kinder('Gebaeude').forEach(geb => {
        const bereich = bereiche.length ? bereichVon(geb) : { start: 0 };
        const nr = proBereich.get(bereich) || 0;
        proBereich.set(bereich, nr + 1);
        animiere(ziel(geb), [
            { opacity: 0, transform: 'translateY(18px) scaleY(0.6)' },
            { opacity: 1, transform: 'translateY(-4px) scaleY(1.06)', offset: 0.6 },
            { opacity: 1, transform: 'none' }
        ], bereich.start + 40 + nr * 60, 360);
    });

    // 3) Icons drop in: cafés first, then bus and bike.
    const einfallen = (el, delay) => animiere(ziel(el), [
        { opacity: 0, transform: 'translateY(-40px) scale(0.6)' },
        { opacity: 1, transform: 'translateY(4px) scale(1.05)', offset: 0.7 },
        { opacity: 1, transform: 'none' }
    ], delay, 420);
    kinder('Kaffee').forEach((el, i) => einfallen(el, introFrame(38) + i * 120));
    [...kinder('Bushaltestellen'), ...kinder('Fahrradstationen')]
        .forEach((el, i) => einfallen(el, introFrame(60) + i * 80));

    // 4) Logo, then all remaining layers fade in.
    animiere(svg.querySelector('g#Logo'),
        [{ opacity: 0 }, { opacity: 0.5, offset: 0.7 }, { opacity: 1 }],
        introFrame(84), introFrame(17), 'linear');
    const keineGrafik = ['defs', 'style', 'title', 'desc', 'metadata'];
    Array.from(svg.children)
        .filter(el => !keineGrafik.includes(el.tagName.toLowerCase()) && !INTRO_EIGENE_ANIMATION.includes(el.id))
        .forEach(el => animiere(el,
            [{ opacity: 0 }, { opacity: 0.4, offset: 0.75 }, { opacity: 1 }],
            introFrame(93), introFrame(28), 'linear'));

    return { finish: () => animationen.forEach(a => { try { a.finish(); } catch (e) { } }) };
}

/** Sets the map view to the intro's final state. */
function jumpToFinalZoom(svg) {
    if (!svg) return;
    const vb = svg.viewBox.baseVal;
    const orig = { width: 1920, height: 1080 };

    // Mobile detection
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
        window.innerWidth <= 768;

    // Mobile: 2.8x zoom (as in the intro: 0.5 + 2.3 * 1), desktop: normal size.
    const finalZoom = isMobile ? 2.8 : 1.0;
    const centerX = isMobile ? orig.width * 0.62 : orig.width / 2;
    const centerY = isMobile ? orig.height * 0.42 : orig.height / 2;

    vb.width = orig.width / finalZoom;
    vb.height = orig.height / finalZoom;
    vb.x = centerX - vb.width / 2;
    vb.y = centerY - vb.height / 2;
}

/** Inserts the map and wires hover, logo, zoom/pan and filters. */
function insertCampusSVG() {
    const container = document.getElementById('lottieMap');
    container.innerHTML = cachedCampusMapSvg || `<p>${t('map.unavailable')}</p>`;
    const svg = container.querySelector('svg');
    if (!svg) return null;

    localizeMapTexts(container);
    svg.classList.add('campus-map-svg');
    applyMapAspectRatio();

    document.getElementById('Button_Pausen')?.remove();

    // Color the question markers by completion status.
    if (typeof window.colorQuizElements === 'function') {
        window.colorQuizElements();
    }

    // Hover effect for all clickable elements.
    const kinderIds = id => Array.from(svg.querySelectorAll(`g#${id} > g`)).map(el => el.id);
    const hoverSelectors = [
        '#lottieMap svg g#Logo:hover',
        ...['Gebaeude', 'Kaffee', 'Fahrradstationen', 'Bushaltestellen'].flatMap(gruppe => {
            const ids = kinderIds(gruppe);
            return CLICKABLE_Geb_CONFIG.lottieMap.exactMatches
                .filter(id => ids.includes(id))
                .map(id => `#lottieMap svg g#${gruppe} > g#${id}:hover`);
        })
    ].join(',\n');
    const hoverStyle = document.createElement('style');
    // Safari does not apply CSS filter functions (brightness()) to inner SVG elements, but url(#…) SVG filters work.
    const dimFilter = document.createElementNS(svg.namespaceURI, 'filter');
    dimFilter.setAttribute('id', 'thl-hover-dim');
    dimFilter.setAttribute('color-interpolation-filters', 'sRGB');
    const transfer = document.createElementNS(svg.namespaceURI, 'feComponentTransfer');
    ['R', 'G', 'B'].forEach(kanal => {
        const fn = document.createElementNS(svg.namespaceURI, `feFunc${kanal}`);
        fn.setAttribute('type', 'linear');
        fn.setAttribute('slope', '0.9');
        transfer.appendChild(fn);
    });
    dimFilter.appendChild(transfer);
    svg.insertBefore(dimFilter, svg.firstChild);
    hoverStyle.textContent = `${hoverSelectors} { filter: url(#thl-hover-dim); }`;
    document.head.appendChild(hoverStyle);

    // Make the whole logo clickable, including the gaps between letters.
    const logoGroup = svg.querySelector('g#Logo');
    if (logoGroup) {
        const bbox = logoGroup.getBBox();
        const rect = document.createElementNS(svg.namespaceURI, 'rect');
        rect.setAttribute('x', bbox.x);
        rect.setAttribute('y', bbox.y);
        rect.setAttribute('width', bbox.width);
        rect.setAttribute('height', bbox.height);
        rect.setAttribute('fill', 'transparent');
        rect.setAttribute('pointer-events', 'all');
        logoGroup.insertBefore(rect, logoGroup.firstChild);
    }

    setupZoomPan();
    initFilters();
    return svg;
}

let mapInitialized = false;

async function initAnimations() {
    if (mapInitialized) return;
    mapInitialized = true;

    // No intro again after a language switch (page reload).
    // Direct link (?show=… / ?info=…): skip the intro and go straight to the target.
    // In the modal (?intro=0, sent by ASK Francis): no intro, only in a tab of its own
    const params = new URLSearchParams(window.location.search);
    const hasDirectLink = params.has('show') || params.has('info');
    const introDisabled = params.get('intro') === '0';
    const animationsOn = areAnimationsEnabled() && !CAME_FROM_LANG_SWITCH && !hasDirectLink && !introDisabled;

    if (!cachedCampusMapSvg) {
        try {
            const r = await fetch('assets/campus_map_v2.svg?v=20261007a');
            if (r.ok) cachedCampusMapSvg = await r.text();
        } catch (e) { }
    }

    const svg = insertCampusSVG();
    if (!svg) return;

    if (!animationsOn) {
        jumpToFinalZoom(svg);
        // Wait one frame so the map has dimensions (flying measures the target).
        if (hasDirectLink) requestAnimationFrame(() => window.campusLegend?.openFromUrl());
        return;
    }

    const intro = runMapIntro(svg);
    const zoom = runIntroZoom(svg, { width: 1920, height: 1080 }, 3000);

    // Skip hint
    const skipHint = document.getElementById('skipIntroHint');
    const isTouchDevice = ('ontouchstart' in window) || navigator.maxTouchPoints > 0;
    let introVorbei = false;
    if (skipHint) {
        // Skip only by click/tap; Space opens the search (legend.js).
        skipHint.textContent = isTouchDevice ? t('intro.skipTap') : t('intro.skipClick');
        // Show after a short delay so the animation has time to start.
        setTimeout(() => { if (!introVorbei) skipHint.classList.add('visible'); }, 400);
    }

    const introBeenden = () => {
        introVorbei = true;
        clearTimeout(introTimeout);
        skipHint?.classList.remove('visible');
        // The skip handlers apply only during the intro; left active, they would swallow the first click afterwards.
        window.removeEventListener('touchstart', onFirstPointer, { capture: true });
        document.removeEventListener('touchstart', onFirstPointer, { capture: true });
        window.removeEventListener('pointerdown', onFirstPointer, { capture: true });
        document.removeEventListener('pointerdown', onFirstPointer, { capture: true });
    };
    const ueberspringen = () => {
        intro.finish();
        zoom.cancel();
        jumpToFinalZoom(svg);
        introBeenden();
    };

    const introTimeout = setTimeout(introBeenden, INTRO_DURATION_MS);

    // Skip by tap/click: cross-origin iframes (e.g. train-on.net) get no keydown while unfocused.
    // pointerdown instead of mousedown because setupZoomPan() calls preventDefault() on pointerdown, which per spec suppresses mousedown/click; capture phase on document fires BEFORE the container handler.
    function onFirstPointer(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        ueberspringen();

        // The map already lies underneath during the intro; the matching pointerup/click would open the element there, so swallow it once.
        const schlucken = ev => { ev.stopPropagation(); ev.stopImmediatePropagation(); };
        ['pointerup', 'click'].forEach(typ => document.addEventListener(typ, schlucken, { capture: true, once: true }));
        setTimeout(() => ['pointerup', 'click'].forEach(typ => document.removeEventListener(typ, schlucken, { capture: true })), 800);
    }
    window.addEventListener('touchstart', onFirstPointer, { passive: false, capture: true });
    document.addEventListener('touchstart', onFirstPointer, { passive: false, capture: true });
    window.addEventListener('pointerdown', onFirstPointer, { passive: false, capture: true });
    document.addEventListener('pointerdown', onFirstPointer, { passive: false, capture: true });
}//initAnimations

// 4) DOMContentLoaded: initAnimations, overlays and the rest.
document.addEventListener('DOMContentLoaded', async () => {
    const el = document.getElementById("footer-container");
    if (el) el.remove(); // remove at once, content is never built

    // Load the map and start the intro.
    initAnimations();

    const offcanvasEl = document.getElementById('buildingInfoOffcanvas');
    offcanvasEl.addEventListener('shown.bs.offcanvas', startBuildingCarousel);

}); //DOMContentLoaded


// Manages the accordion toggle.
function setupAccordionToggle(modal) {
    const infoIconContainer = modal.querySelector('.info-icon-trigger');
    const infoIcon = modal.querySelector('.info-icon-trigger .fas.fa-info-circle');
    const collapseElement = modal.querySelector('#campusInfosOverlay');

    if (infoIcon && collapseElement && infoIconContainer) {
        // Remove all event listeners by cloning the element.
        const newContainer = infoIconContainer.cloneNode(true);
        infoIconContainer.parentNode.replaceChild(newContainer, infoIconContainer);

        // Get fresh references.
        const freshContainer = modal.querySelector('.info-icon-trigger');
        const freshCollapseElement = modal.querySelector('#campusInfosOverlay');

        // Updates the UI.
        function updateUI() {
            if (freshCollapseElement.classList.contains('show')) {
                freshContainer.innerHTML = `<div class="campus-accordion-close"><i class="fas fa-info-circle campus-info-icon"></i><span>${t('common.close')}</span></div>`;
                freshContainer.style.padding = '10px 12px';

                // Add the listener for the new icon.
                const newIcon = freshContainer.querySelector('.fas.fa-info-circle');
                if (newIcon) {
                    newIcon.addEventListener('click', function (e) {
                        e.preventDefault();
                        e.stopPropagation();

                        if (freshCollapseElement.classList.contains('show')) {
                            freshCollapseElement.classList.remove('show');
                        } else {
                            freshCollapseElement.classList.add('show');
                        }
                        updateUI();
                    });
                }

                // Add the listener for the "close" text.
                const closeText = freshContainer.querySelector('span');
                if (closeText) {
                    closeText.addEventListener('click', function (e) {
                        e.preventDefault();
                        e.stopPropagation();

                        if (freshCollapseElement.classList.contains('show')) {
                            freshCollapseElement.classList.remove('show');
                        } else {
                            freshCollapseElement.classList.add('show');
                        }
                        updateUI();
                    });
                }
            } else {
                // Accordion closed: show only the icon.
                freshContainer.innerHTML = '<i class="fas fa-info-circle campus-info-icon"></i>';
                freshContainer.style.padding = '10px';

                // Add the listener for the new icon.
                const newIcon = freshContainer.querySelector('.fas.fa-info-circle');
                if (newIcon) {
                    newIcon.addEventListener('click', function (e) {
                        e.preventDefault();
                        e.stopPropagation();

                        if (freshCollapseElement.classList.contains('show')) {
                            freshCollapseElement.classList.remove('show');
                        } else {
                            freshCollapseElement.classList.add('show');
                        }
                        updateUI();
                    });
                }
            }
        }

        // Remove Bootstrap attributes.
        freshContainer.removeAttribute('data-bs-toggle');
        freshContainer.removeAttribute('data-bs-target');
        freshContainer.removeAttribute('aria-expanded');

        // Add the listener for the icon.
        const iconElement = freshContainer.querySelector('.fas.fa-info-circle');
        if (iconElement) {
            iconElement.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                // Simply toggle the show class.
                if (freshCollapseElement.classList.contains('show')) {
                    // Close
                    freshCollapseElement.classList.remove('show');
                } else {
                    // Open
                    freshCollapseElement.classList.add('show');
                }

                // Update the UI immediately.
                updateUI();
            });
        }

        // Set the initial UI.
        updateUI();
    }
}

// ========================================
// Quiz progress and marker coloring
// ========================================

const COMPLETED_QUIZZES_STORAGE_KEY = 'quiz_completed_ids';

// Global quiz progress state.
let completedQuizzesCount = 0;

// localStorage helper.
function getCompletedQuizIds() {
    const stored = localStorage.getItem(COMPLETED_QUIZZES_STORAGE_KEY);
    const ids = stored ? JSON.parse(stored) : [];
    return ids.map(id => String(id));
}

// Colors the question markers by quiz completion; map: SVG marker id → quiz id in quizModals.
window.colorQuizElements = function () {
    const completedIds = getCompletedQuizIds();

    const quizMapping = {
        'Frage': 'Frage',
        'Frage-2': 'Frage2',
        'Frage-3': 'Frage3',
        'Frage-4': 'Frage4',
        'Frage-5': 'Frage5',
        'Frage-6': 'Frage6',
        'Frage-7': 'Frage7',
        'Frage-8': 'Frage8',
        'Frage-9': 'Frage9',
        'Frage-10': 'Frage10'
    };

    Object.keys(quizMapping).forEach(frageId => {
        const quizId = quizMapping[frageId];
        const isCompleted = completedIds.includes(quizId);

        const frageGruppe = document.querySelector(`#${frageId}`);

        if (!frageGruppe) {
            return;
        }

        let sprechblase = frageGruppe.querySelector('[id^="Sprechblase"]');

        if (sprechblase) {
            if (isCompleted) {
                if (sprechblase.tagName === 'g') {
                    const pathInGroup = sprechblase.querySelector('path');
                    if (pathInGroup) {
                        pathInGroup.setAttribute('fill', '#4B5459');
                        pathInGroup.setAttribute('stroke', '#4B5459');
                    }
                }
                else if (sprechblase.tagName === 'path') {
                    sprechblase.setAttribute('fill', '#4B5459');
                    sprechblase.setAttribute('stroke', '#4B5459');
                }

                const allPaths = frageGruppe.querySelectorAll('path');

                allPaths.forEach(path => {
                    const currentFill = path.getAttribute('fill');
                    const pathId = path.getAttribute('id');

                    const isSprechblasePath = pathId && pathId.startsWith('Sprechblase');
                    const isInsideSprechblase = path.closest('[id^="Sprechblase"]');

                    if (!isSprechblasePath && !isInsideSprechblase && currentFill === '#4b5459') {
                        path.setAttribute('fill', '#fff');
                    }
                });
            }
        }
    });
}

function addCompletedQuizId(quizId) {
    const completedIds = getCompletedQuizIds();
    const idString = String(quizId);

    if (!completedIds.includes(idString)) {
        completedIds.push(idString);
        localStorage.setItem(COMPLETED_QUIZZES_STORAGE_KEY, JSON.stringify(completedIds));

        completedQuizzesCount++;

        // Recolor the question markers.
        if (typeof window.colorQuizElements === 'function') {
            window.colorQuizElements();
        }

        const badgesOffcanvas = document.getElementById('badgesOffcanvas');
        if (badgesOffcanvas && badgesOffcanvas.classList.contains('show')) {
            renderBadgesOverview();
        }

        return true;
    }

    return false;
}

function initCompletedQuizzesCounter() {
    const completedIds = getCompletedQuizIds();
    completedQuizzesCount = completedIds.length;
}

document.addEventListener('DOMContentLoaded', function () {
    initCompletedQuizzesCounter();

    // Badge button listener.
    const badgeBtn = document.getElementById('toolboxBadgesBtn');
    if (badgeBtn) {
        badgeBtn.addEventListener('click', function () {
            // Render Badges
            renderBadgesOverview();

            // Open the offcanvas.
            const badgesOffcanvas = new bootstrap.Offcanvas(document.getElementById('badgesOffcanvas'));
            badgesOffcanvas.show();
        });
    }

    // Menu button (phone only): expands language, badges and settings.
    const menu = document.getElementById('toolboxMenu');
    const menuBtn = document.getElementById('toolboxMenuBtn');
    if (menu && menuBtn) {
        const setMenuOpen = open => {
            menu.classList.toggle('open', open);
            menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        };
        menuBtn.addEventListener('click', () => setMenuOpen(!menu.classList.contains('open')));
        // Close after an entry is chosen.
        document.getElementById('toolbox').addEventListener('click', e => {
            if (e.target.closest('button')) setMenuOpen(false);
        });
        document.addEventListener('click', e => {
            if (!menu.contains(e.target)) setMenuOpen(false);
        });
        menu.addEventListener('keydown', e => {
            if (e.key === 'Escape' && menu.classList.contains('open')) {
                setMenuOpen(false);
                menuBtn.focus();
            }
        });
    }

    // No blur() after closing the panels: keyboard users would lose their position (focus on <body>); :focus-visible already hides the ring after mouse clicks, and a11y.js returns focus to the badges button.

    // Animations toggle
    const animationsToggle = document.getElementById('animationsToggle');
    if (animationsToggle) {
        const enabled = areAnimationsEnabled();
        animationsToggle.checked = enabled;
        const card = animationsToggle.closest('.filter-card');
        if (card) card.classList.toggle('active', enabled);

        animationsToggle.addEventListener('change', (e) => {
            const on = e.target.checked;
            localStorage.setItem(ANIMATIONS_STORAGE_KEY, String(on));
            applyAnimationsPreference();
            if (card) card.classList.toggle('active', on);
        });
    }

    // Reset progress button opens the confirmation modal.
    const resetProgressBtn = document.getElementById('resetProgressBtn');
    const resetConfirmModalEl = document.getElementById('resetConfirmModal');
    if (resetProgressBtn && resetConfirmModalEl) {
        resetProgressBtn.addEventListener('click', function () {
            bootstrap.Modal.getOrCreateInstance(resetConfirmModalEl).show();
        });
    }

    // Confirm button in the modal performs the reset.
    const confirmResetBtn = document.getElementById('confirmResetBtn');
    if (confirmResetBtn) {
        confirmResetBtn.addEventListener('click', function () {
            localStorage.removeItem(COMPLETED_QUIZZES_STORAGE_KEY);
            localStorage.removeItem('filter_settings_v3');
            localStorage.removeItem(ANIMATIONS_STORAGE_KEY);
            window.location.reload();
        });
    }
});

// Wire the accordion toggle for the campus info in each modal.
document.addEventListener('shown.bs.modal', (e) => {
    setupAccordionToggle(e.target);
});


function getProgressiveBadge(count) {
    return ALL_BADGES.find(b => b.milestone === count) || null;
}

function renderBadgesOverview() {
    const container = document.getElementById('badgesContent');
    if (!container) return;

    const currentCount = completedQuizzesCount;
    let html = '';

    ALL_BADGES.forEach(badge => {
        const isUnlocked = currentCount >= badge.milestone;
        const progress = Math.min(currentCount, badge.milestone);
        const progressPercent = (progress / badge.milestone) * 100;
        const remaining = badge.milestone - currentCount;

        html += `
  <div class="badge-card ${isUnlocked ? 'unlocked' : 'locked'}">
    <div class="badge-icon-container">
      <img src="${badge.url}" alt="">
    </div>
    <div class="badge-info">
      <h3 class="badge-name">${badge.name}</h3>
      <p class="badge-description">${badge.description}</p>
      <div class="badge-progress">
        <div class="progress-text">
          <span>${t('badges.quizzes', { n: progress, total: badge.milestone })}</span>
          <span>${Math.round(progressPercent)}%</span>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar-fill" style="width: ${progressPercent}%"></div>
        </div>
      </div>
      ${isUnlocked
                ? `<div class="badge-date">${t('badges.achieved')}</div>`
                : remaining > 0
                    ? `<div class="badge-hint">${remaining === 1 ? t('badges.remainingOne') : t('badges.remainingMany', { n: remaining })}</div>`
                    : ''
            }
    </div>
  </div>
`;
    });

    container.innerHTML = html;
}

function showBadgeNotification() {
    const badge = getProgressiveBadge(completedQuizzesCount);

    if (!badge) return;

    const existingNotification = document.querySelector('.badge-notification');
    if (existingNotification) existingNotification.remove();

    const notification = document.createElement('div');
    notification.className = 'badge-notification';
    notification.setAttribute('role', 'status');
    notification.setAttribute('aria-live', 'polite');

    notification.innerHTML = `
<div class="badge-content">
  <img src="${badge.url}" alt="" class="badge-svg">
  <div class="badge-text">
    ${t('badges.earned')} <span class="badge-name">${badge.name}</span>
  </div>
</div>
<button type="button" class="close-btn" aria-label="${t('badges.closeNotification')}" onclick="closeBadgeNotification()">&times;</button>
<div class="countdown-timer" id="countdown-timer"></div>
`;

    document.body.appendChild(notification);

    const badgeContent = notification.querySelector('.badge-content');
    badgeContent.addEventListener('click', function () {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        });

        closeBadgeNotification();

        setTimeout(() => {
            renderBadgesOverview();
            const badgesOffcanvas = new bootstrap.Offcanvas(document.getElementById('badgesOffcanvas'));
            badgesOffcanvas.show();
        }, 300);
    });

    startCountdownTimer(notification);
}

function startCountdownTimer(notification) {
    const timer = notification.querySelector('#countdown-timer');
    let timeLeft = 10;

    notification.countdownInterval = setInterval(() => {
        timer.style.width = ((timeLeft -= 0.1) / 10 * 100) + '%';
        if (timeLeft <= 0) {
            clearInterval(notification.countdownInterval);
            closeBadgeNotification();
        }
    }, 100);
}

function closeBadgeNotification() {
    const n = document.querySelector('.badge-notification');
    if (n) {
        if (n.countdownInterval) clearInterval(n.countdownInterval);
        n.remove();
    }
}
