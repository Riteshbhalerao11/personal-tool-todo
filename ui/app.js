// app.js - Todo Widget frontend logic

let uiFontSize = 14;
let todoFontSize = 15;
let todayDate = '';
let isRefreshing = false;
let currentPersona = 'ritesh';
let honeyPotMode = false;
let inputCollapsed = false;
let quoteCollapsed = false;
let settingsOpen = false;
let inputDepth = 0;
let isEditingHoneyMsg = false;
let poemViewOpen = false;
let actionVersion = 0;
let undoStack = [];
let lastRenderedItems = [];
const UNDO_MAX = 30;

// ---- Pywebview bridge ----

async function api(method, ...args) {
    if (!window.pywebview || !window.pywebview.api) {
        console.warn('pywebview API not ready');
        return null;
    }
    return await window.pywebview.api[method](...args);
}

// ---- Initialization ----

async function init() {
    const data = await api('get_initial_data');
    if (!data) return;

    currentPersona = data.persona || 'ritesh';
    todayDate = data.date;
    uiFontSize = data.uiFontSize || 14;
    todoFontSize = data.todoFontSize || 15;
    applyFontSizes();

    // Apply theme
    if (currentPersona === 'riya') {
        document.documentElement.setAttribute('data-theme', 'riya');
        document.getElementById('widget-title').textContent = "Riya's Todos";
    }

    document.getElementById('streak-text').textContent = data.streak_display;
    document.getElementById('greeting-text').textContent = data.greeting;

    renderQuote(data.quote);

    renderTodos(data.items, true);
}

// ---- Quote rendering ----

function renderQuote(quote) {
    if (!quote) return;
    document.getElementById('quote-text').textContent = '"' + quote.text + '"';
    document.getElementById('quote-author').textContent = '- ' + quote.author;
}

// ---- Separate collapse toggles ----

function toggleInputArea() {
    inputCollapsed = !inputCollapsed;
    const addArea = document.getElementById('add-area');
    const toggle = document.getElementById('setting-show-input');

    if (inputCollapsed) {
        addArea.style.display = 'none';
    } else {
        // Don't show add-area if in honey pot mode and persona is riya
        if (!(honeyPotMode && currentPersona === 'riya')) {
            addArea.style.display = '';
        }
    }
    if (toggle) toggle.checked = !inputCollapsed;
}

function toggleQuoteArea() {
    quoteCollapsed = !quoteCollapsed;
    const streakArea = document.getElementById('streak-area');
    const quoteArea = document.getElementById('quote-area');
    const toggle = document.getElementById('setting-show-quote');

    if (quoteCollapsed) {
        streakArea.style.display = 'none';
        quoteArea.style.display = 'none';
    } else {
        // Don't show if in honey pot mode
        if (!honeyPotMode) {
            streakArea.style.display = '';
            quoteArea.style.display = '';
        }
    }
    if (toggle) toggle.checked = !quoteCollapsed;
}

// ---- Todo rendering ----

function mdToHtml(text) {
    // ***bold italic***
    text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<b><i>$1</i></b>');
    // **bold**
    text = text.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    // *italic*
    text = text.replace(/\*(.+?)\*/g, '<i>$1</i>');
    // <u> and <s> pass through
    return text;
}

function htmlToMd(html) {
    let text = html;
    text = text.replace(/<strong>/gi, '<b>').replace(/<\/strong>/gi, '</b>');
    text = text.replace(/<em>/gi, '<i>').replace(/<\/em>/gi, '</i>');
    text = text.replace(/<b><i>(.+?)<\/i><\/b>/gi, '***$1***');
    text = text.replace(/<i><b>(.+?)<\/b><\/i>/gi, '***$1***');
    text = text.replace(/<b>(.+?)<\/b>/gi, '**$1**');
    text = text.replace(/<i>(.+?)<\/i>/gi, '*$1*');
    // Keep <u> and <s> as-is
    text = text.replace(/<(?!\/?[us]>)[^>]+>/gi, '');
    text = text.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
    text = text.replace(/<br\s*\/?>/gi, ' ');
    return text.trim();
}

let dragFromIndex = null;
let dragGroupSize = 1;

function renderTodos(items, skipUndo) {
    if (!skipUndo && items && items.length >= 0) {
        // Save current state to undo stack before rendering new state
        pushUndo();
    }
    lastRenderedItems = items ? JSON.parse(JSON.stringify(items)) : [];
    const list = document.getElementById('todo-list');
    list.innerHTML = '';

    if (!items || items.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        const messages = [
            "Nothing here yet - add your first todo!",
            "A clean slate! What will you accomplish?",
            "Your sticky note is blank. Write something!",
            "No todos yet. The pen is waiting...",
        ];
        empty.textContent = messages[Math.floor(Math.random() * messages.length)];
        list.appendChild(empty);

        const carryBtn = document.createElement('button');
        carryBtn.className = 'carry-over-btn';
        carryBtn.textContent = "Load yesterday's todos";
        carryBtn.onclick = async () => {
            const myVersion = ++actionVersion;
            const newItems = await api('load_yesterday');
            if (myVersion !== actionVersion) return;
            if (newItems) renderTodos(newItems);
        };
        list.appendChild(carryBtn);
        return;
    }

    items.forEach((item, index) => {
        const depth = item.depth || 0;
        const row = document.createElement('div');
        row.className = 'todo-item' + (depth > 0 ? ' nested' : '');
        row.dataset.index = index;
        if (depth > 0) {
            row.style.paddingLeft = (depth * 20 + 4) + 'px';
        }

        // Drag handle
        const handle = document.createElement('span');
        handle.className = 'drag-handle';
        handle.textContent = '\u2847';
        handle.title = 'Drag to reorder';
        handle.addEventListener('mousedown', () => { row.draggable = true; });

        row.addEventListener('dragstart', (e) => {
            dragFromIndex = index;
            // Calculate group size: parent + all deeper children following it
            dragGroupSize = 1;
            const parentDepth = depth;
            for (let k = index + 1; k < items.length; k++) {
                if ((items[k].depth || 0) > parentDepth) dragGroupSize++;
                else break;
            }
            // Apply dragging class to entire group
            for (let k = 0; k < dragGroupSize; k++) {
                const el = list.children[index + k];
                if (el) el.classList.add('dragging');
            }
            e.dataTransfer.effectAllowed = 'move';
        });
        row.addEventListener('dragend', () => {
            row.draggable = false;
            dragFromIndex = null;
            list.querySelectorAll('.dragging, .drag-over-top, .drag-over-bottom').forEach(el => {
                el.classList.remove('dragging', 'drag-over-top', 'drag-over-bottom');
            });
        });
        row.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            if (dragFromIndex === null) return;
            // Don't allow dropping onto items within the dragged group
            if (index >= dragFromIndex && index < dragFromIndex + dragGroupSize) return;
            const rect = row.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            row.classList.toggle('drag-over-top', e.clientY < midY);
            row.classList.toggle('drag-over-bottom', e.clientY >= midY);
        });
        row.addEventListener('dragleave', () => {
            row.classList.remove('drag-over-top', 'drag-over-bottom');
        });
        row.addEventListener('drop', async (e) => {
            e.preventDefault();
            row.classList.remove('drag-over-top', 'drag-over-bottom');
            if (dragFromIndex === null) return;
            if (index >= dragFromIndex && index < dragFromIndex + dragGroupSize) return;
            const rect = row.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            let toIndex;
            if (e.clientY >= midY && dragFromIndex < index) {
                toIndex = index;
            } else if (e.clientY >= midY && dragFromIndex > index) {
                toIndex = index + 1;
            } else if (e.clientY < midY && dragFromIndex < index) {
                toIndex = index - 1;
            } else {
                toIndex = index;
            }
            const myVersion = ++actionVersion;
            const result = await api('reorder_todo_group', dragFromIndex, toIndex);
            if (myVersion !== actionVersion) return;
            if (result) renderTodos(result);
            dragFromIndex = null;
        });

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = item.done;
        cb.addEventListener('change', () => toggleTodo(index, cb.checked));

        const span = document.createElement('span');
        span.className = 'todo-text' + (item.done ? ' done' : '');
        span.contentEditable = 'true';
        span.innerHTML = mdToHtml(item.text);
        span.dataset.index = index;
        span.dataset.depth = depth;

        span.addEventListener('blur', async () => {
            const newText = htmlToMd(span.innerHTML);
            if (newText === item.text) return;
            // Find current index by matching original text+depth (guards against stale index)
            let currentIndex = -1;
            for (let i = 0; i < lastRenderedItems.length; i++) {
                if (lastRenderedItems[i].text === item.text && (lastRenderedItems[i].depth || 0) === depth) {
                    currentIndex = i;
                    break;
                }
            }
            if (currentIndex === -1) return; // item was deleted, drop silently
            const myVersion = ++actionVersion;
            const result = await api('update_todo_text', currentIndex, newText);
            if (myVersion !== actionVersion) return;
            if (result) renderTodos(result, true); // skipUndo for inline text edits
        });

        span.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                span.blur();
            }
            // Tab = indent, Shift+Tab = outdent
            if (e.key === 'Tab') {
                e.preventDefault();
                const curDepth = parseInt(span.dataset.depth) || 0;
                const newDepth = e.shiftKey ? Math.max(0, curDepth - 1) : Math.min(3, curDepth + 1);
                if (newDepth !== curDepth) {
                    const myVersion = ++actionVersion;
                    const items = await api('set_todo_depth', index, newDepth);
                    if (myVersion !== actionVersion) return;
                    if (items) renderTodos(items);
                }
            }
            // ArrowDown = create child subtask
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                const myVersion = ++actionVersion;
                // Save any pending edits first
                const curText = htmlToMd(span.innerHTML);
                if (curText !== item.text) {
                    await api('update_todo_text', index, curText);
                    if (myVersion !== actionVersion) return;
                }
                const curDepth = parseInt(span.dataset.depth) || 0;
                const childDepth = Math.min(3, curDepth + 1);
                const items = await api('insert_todo_after', index, '', childDepth);
                if (myVersion !== actionVersion) return;
                if (items) {
                    renderTodos(items);
                    // Focus the newly created child item
                    requestAnimationFrame(() => {
                        const newSpan = document.querySelector(`.todo-text[data-index="${index + 1}"]`);
                        if (newSpan) newSpan.focus();
                    });
                }
            }
        });

        const del = document.createElement('button');
        del.className = 'delete-btn';
        del.textContent = 'x';
        del.title = 'Delete';
        del.addEventListener('click', () => deleteTodo(index));

        // Right-click context menu
        row.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu(e.clientX, e.clientY, index, depth);
        });

        row.appendChild(handle);
        row.appendChild(cb);
        row.appendChild(span);
        row.appendChild(del);
        list.appendChild(row);
    });
}

// ---- Context Menu ----

function showContextMenu(x, y, index, depth) {
    hideContextMenu();
    const menu = document.createElement('div');
    menu.id = 'context-menu';

    const addChildOption = document.createElement('div');
    addChildOption.className = 'context-menu-item';
    addChildOption.textContent = 'Add Child';
    if (depth >= 3) {
        addChildOption.classList.add('disabled');
        addChildOption.title = 'Max depth reached';
    }
    addChildOption.addEventListener('click', async () => {
        hideContextMenu();
        if (depth >= 3) return;
        const myVersion = ++actionVersion;
        const childDepth = Math.min(3, depth + 1);
        const items = await api('insert_todo_after', index, '', childDepth);
        if (myVersion !== actionVersion) return;
        if (items) {
            renderTodos(items);
            requestAnimationFrame(() => {
                const newSpan = document.querySelector(`.todo-text[data-index="${index + 1}"]`);
                if (newSpan) newSpan.focus();
            });
        }
    });

    const deleteOption = document.createElement('div');
    deleteOption.className = 'context-menu-item danger';
    deleteOption.textContent = 'Delete';
    deleteOption.addEventListener('click', () => {
        hideContextMenu();
        deleteTodo(index);
    });

    menu.appendChild(addChildOption);
    menu.appendChild(deleteOption);
    document.body.appendChild(menu);

    // Position: ensure it stays within viewport
    const menuRect = menu.getBoundingClientRect();
    if (x + menuRect.width > window.innerWidth) x = window.innerWidth - menuRect.width - 4;
    if (y + menuRect.height > window.innerHeight) y = window.innerHeight - menuRect.height - 4;
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';

    // Close on click outside
    setTimeout(() => {
        document.addEventListener('mousedown', hideContextMenuOnOutside);
    }, 0);
}

function hideContextMenu() {
    const existing = document.getElementById('context-menu');
    if (existing) existing.remove();
    document.removeEventListener('mousedown', hideContextMenuOnOutside);
}

function hideContextMenuOnOutside(e) {
    const menu = document.getElementById('context-menu');
    if (menu && !menu.contains(e.target)) {
        hideContextMenu();
    }
}

// ---- Undo Stack ----

function pushUndo() {
    if (lastRenderedItems.length > 0 || undoStack.length === 0) {
        undoStack.push(JSON.parse(JSON.stringify(lastRenderedItems)));
        if (undoStack.length > UNDO_MAX) undoStack.shift();
    }
}

async function undo() {
    if (undoStack.length === 0 || honeyPotMode) return;
    const prev = undoStack.pop();
    const myVersion = ++actionVersion;
    const items = await api('restore_todos', prev);
    if (myVersion !== actionVersion) return;
    if (items) renderTodos(items, true);

    const streakData = await api('get_streak_data');
    if (myVersion !== actionVersion) return;
    if (streakData) {
        document.getElementById('streak-text').textContent = streakData.display;
    }
}

// ---- Actions ----

function handleAdd() {
    if (honeyPotMode) {
        addToHoneyPot();
    } else {
        addTodo();
    }
}

async function addTodo() {
    const el = document.getElementById('new-todo');
    const html = el.innerHTML.trim();

    // Enter on empty input at depth > 0 resets depth
    if ((!html || html === '<br>') && inputDepth > 0) {
        inputDepth = 0;
        updateInputDepthVisual();
        return;
    }
    if (!html || html === '<br>') return;

    const text = htmlToMd(html);
    if (!text) return;

    const myVersion = ++actionVersion;
    const items = inputDepth > 0
        ? await api('add_todo_at_depth', text, inputDepth)
        : await api('add_todo', text);
    if (myVersion !== actionVersion) return;
    if (items) renderTodos(items);
    el.innerHTML = '';
    el.focus();

    const streakData = await api('get_streak_data');
    if (myVersion !== actionVersion) return;
    if (streakData) {
        document.getElementById('streak-text').textContent = streakData.display;
    }
}

async function toggleTodo(index, done) {
    const myVersion = ++actionVersion;
    const items = await api('toggle_todo', index, done);
    if (myVersion !== actionVersion) return; // stale response, discard
    if (items) renderTodos(items);

    const streakData = await api('get_streak_data');
    if (myVersion !== actionVersion) return;
    if (streakData) {
        document.getElementById('streak-text').textContent = streakData.display;
    }
}

async function deleteTodo(index) {
    const myVersion = ++actionVersion;
    const items = await api('delete_todo', index);
    if (myVersion !== actionVersion) return;
    if (items) renderTodos(items);
}

async function clearAllTodos() {
    const myVersion = ++actionVersion;
    if (honeyPotMode) {
        const messages = await api('confirm_and_clear_honey_pot');
        if (myVersion !== actionVersion) return;
        if (messages) renderHoneyPotMessages(messages);
    } else {
        const items = await api('confirm_and_clear_todos');
        if (myVersion !== actionVersion) return;
        if (items) renderTodos(items);
    }
}

// ---- Formatting (applies to focused contenteditable) ----

function fmt(command) {
    document.execCommand(command, false, null);
}

function applyFontSizeToSelection(size) {
    if (!size) return;
    document.execCommand('fontSize', false, size);
}

// ---- Emoji Picker ----

const EMOJI_CATEGORIES = {
    'Smileys':  ['😀','😂','🥹','😊','😍','🥰','😘','😜','🤪','😎','🤩','🥳','😤','😭','🥺','😱','🤔','🫣','🤭','😴','🙄','😈'],
    'Hearts':   ['❤️','🧡','💛','💚','💙','💜','🖤','🤍','💕','💞','💓','💗','💖','💘','💝','♥️','🫶','💑','💏'],
    'Hands':    ['👍','👎','👏','🙌','🤝','✌️','🤞','🫰','👋','🙏','💪','👊','✊','🫡','🤙','👌','☝️'],
    'People':   ['🙂','🙃','😇','🤓','🧐','🥸','🤠','🫠','😵‍💫','🤯','🥱','🫥','👻','💀','🤖','👽','🎅','🧚'],
    'Nature':   ['🌸','🌺','🌻','🌹','🌷','🪻','🌼','🍀','🌿','🌱','🌳','🍃','🦋','🐝','🌈','⭐','🌙','☀️','🔥','💧','❄️'],
    'Food':     ['🍕','🍔','🍟','🌮','🍣','🍩','🍰','🧁','🍪','☕','🧋','🍷','🥂','🍾','🎂','🍫','🍓','🍑','🥑','🫐'],
    'Objects':  ['🎯','🏆','🎉','🎊','🎵','🎶','📌','📝','💡','🔔','⏰','📅','✅','❌','⚡','🚀','💻','📱','🎮','🛒','💰','🎁'],
};

let emojiPickerOpen = false;

function toggleEmojiPicker() {
    const picker = document.getElementById('emoji-picker');
    emojiPickerOpen = !emojiPickerOpen;
    if (emojiPickerOpen) {
        picker.classList.add('open');
        const cats = Object.keys(EMOJI_CATEGORIES);
        renderEmojiTabs(cats, cats[0]);
        renderEmojiGrid(cats[0]);
    } else {
        picker.classList.remove('open');
    }
}

function renderEmojiTabs(categories, active) {
    const tabs = document.getElementById('emoji-tabs');
    // Only build tabs once, then just toggle active class
    if (tabs.children.length === 0) {
        categories.forEach(cat => {
            const btn = document.createElement('button');
            btn.textContent = EMOJI_CATEGORIES[cat][0] + ' ' + cat;
            btn.dataset.cat = cat;
            btn.onmousedown = (e) => {
                e.preventDefault();
                // Toggle active class without rebuilding
                tabs.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderEmojiGrid(cat);
            };
            tabs.appendChild(btn);
        });
    }
    tabs.querySelectorAll('button').forEach(b => {
        b.classList.toggle('active', b.dataset.cat === active);
    });
}

function renderEmojiGrid(category) {
    const grid = document.getElementById('emoji-grid');
    grid.innerHTML = '';
    (EMOJI_CATEGORIES[category] || []).forEach(emoji => {
        const btn = document.createElement('button');
        btn.textContent = emoji;
        btn.onmousedown = (e) => {
            e.preventDefault();
            insertEmoji(emoji);
        };
        grid.appendChild(btn);
    });
}

function insertEmoji(emoji) {
    const input = document.getElementById('new-todo');
    input.focus();
    document.execCommand('insertText', false, emoji);
    // Close picker
    emojiPickerOpen = false;
    document.getElementById('emoji-picker').classList.remove('open');
}

// Close emoji picker on click outside
document.addEventListener('mousedown', (e) => {
    if (!emojiPickerOpen) return;
    const picker = document.getElementById('emoji-picker');
    const btn = document.getElementById('emoji-btn');
    if (!picker.contains(e.target) && e.target !== btn) {
        emojiPickerOpen = false;
        picker.classList.remove('open');
    }
});

// ---- Minimize to tray ----

function minimizeWidget() {
    api('minimize_to_tray');
}

// ---- Font sizes (two independent controls) ----

function changeUiFontSize(delta) {
    uiFontSize = Math.max(10, Math.min(22, uiFontSize + delta));
    applyFontSizes();
    api('set_ui_font_size', uiFontSize);
    const label = document.getElementById('ui-font-label');
    if (label) label.textContent = uiFontSize + 'px';
}

function changeTodoFontSize(delta) {
    todoFontSize = Math.max(11, Math.min(26, todoFontSize + delta));
    applyFontSizes();
    api('set_todo_font_size', todoFontSize);
    const label = document.getElementById('todo-font-label');
    if (label) label.textContent = todoFontSize + 'px';
}

function applyFontSizes() {
    document.documentElement.style.setProperty('--ui-font-size', uiFontSize + 'px');
    document.documentElement.style.setProperty('--todo-font-size', todoFontSize + 'px');
}

function updateInputDepthVisual() {
    const input = document.getElementById('new-todo');
    const indicator = document.getElementById('depth-indicator');
    input.style.paddingLeft = (6 + inputDepth * 20) + 'px';
    if (inputDepth > 0) {
        indicator.textContent = '\u21B3'.repeat(inputDepth);
        indicator.classList.add('visible');
    } else {
        indicator.textContent = '';
        indicator.classList.remove('visible');
    }
}

// ---- Honey Pot ----

async function toggleHoneyPot() {
    honeyPotMode = !honeyPotMode;

    const toggle = document.getElementById('honey-toggle');
    toggle.classList.toggle('active', honeyPotMode);

    await api('set_honey_pot_mode', honeyPotMode);

    if (honeyPotMode) {
        if (currentPersona === 'riya') {
            // Riya gets the full Pooh transition
            const overlay = document.getElementById('honey-transition');

            // Force GIF to replay by resetting src with cache buster
            const gif = document.getElementById('pooh-gif');
            gif.src = 'assets/pooh.gif?' + Date.now();

            overlay.classList.add('show');

            // Play Pooh voice
            const sound = document.getElementById('honey-sound');
            if (sound) { sound.currentTime = 0; sound.play().catch(() => {}); }

            setTimeout(async () => {
                overlay.classList.remove('show');
                // Wait for fade-out to finish before switching view
                setTimeout(async () => {
                    enterHoneyPotView();
                    await loadHoneyPotMessages();
                }, 600);
            }, 2000);
        } else {
            // Ritesh: no transition, just switch view
            enterHoneyPotView();
            // Ritesh keeps the input for writing messages
            document.getElementById('new-todo').dataset.placeholder = 'Write a message for Riya...';
            await loadHoneyPotMessages();
        }
    } else {
        exitHoneyPotView();
    }
}

function enterHoneyPotView() {
    document.getElementById('widget-title').textContent = 'Honey Pot';
    document.getElementById('streak-area').style.display = 'none';
    document.getElementById('quote-area').style.display = 'none';
    document.getElementById('todo-area').classList.add('honeypot-bg');

    if (currentPersona === 'riya') {
        // Riya: hide add area entirely (read-only, Ritesh adds via MD or his app)
        document.getElementById('add-area').style.display = 'none';
    } else {
        // Ritesh: show input to write messages to honey pot
        document.getElementById('add-area').style.display = '';
        document.getElementById('new-todo').dataset.placeholder = 'Write a message for Riya...';
    }
}

function exitHoneyPotView() {
    const titleText = currentPersona === 'riya' ? "Riya's Todos" : 'My Todos';
    document.getElementById('widget-title').textContent = titleText;
    document.getElementById('new-todo').dataset.placeholder = 'Write something...';
    document.getElementById('todo-area').classList.remove('honeypot-bg');

    // Restore areas based on their individual toggle states
    document.getElementById('streak-area').style.display = quoteCollapsed ? 'none' : '';
    document.getElementById('quote-area').style.display = quoteCollapsed ? 'none' : '';
    document.getElementById('add-area').style.display = inputCollapsed ? 'none' : '';

    // Reload todos
    (async () => {
        const data = await api('get_initial_data');
        if (data) {
            document.getElementById('streak-text').textContent = data.streak_display;
            renderTodos(data.items, true);
        }
    })();
}

async function loadHoneyPotMessages() {
    const messages = await api('get_honey_pot_messages');
    renderHoneyPotMessages(messages || []);
}

function renderHoneyPotMessages(messages) {
    const list = document.getElementById('todo-list');
    list.innerHTML = '';

    if (!messages || messages.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        if (currentPersona === 'riya') {
            empty.textContent = 'No messages yet... the honey pot is empty!';
        } else {
            empty.textContent = 'No messages yet - write something sweet!';
        }
        list.appendChild(empty);
        return;
    }

    // Show most recent first
    const reversed = messages.slice().reverse();
    reversed.forEach((msg, i) => {
        const realIndex = messages.length - 1 - i;
        const div = document.createElement('div');
        div.className = 'honey-message';

        const content = document.createElement('div');
        content.className = 'msg-content';

        const text = document.createElement('div');
        text.className = 'msg-text';
        text.innerHTML = mdToHtml(msg.text);

        // Ritesh can edit his own messages inline
        if (msg.from === 'ritesh' && currentPersona === 'ritesh') {
            text.contentEditable = 'true';
            text.addEventListener('focus', () => { isEditingHoneyMsg = true; });
            text.addEventListener('blur', async () => {
                isEditingHoneyMsg = false;
                const newText = htmlToMd(text.innerHTML);
                if (newText === msg.text) return;
                const result = await api('update_honey_pot_msg', realIndex, newText);
                if (result) renderHoneyPotMessages(result);
            });
            text.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    text.blur();
                }
            });
        }

        const meta = document.createElement('div');
        meta.className = 'msg-meta';
        meta.textContent = msg.date;

        content.appendChild(text);
        content.appendChild(meta);
        div.appendChild(content);

        // Only author can delete their own messages
        if (msg.from === currentPersona) {
            const del = document.createElement('button');
            del.className = 'delete-btn';
            del.textContent = 'x';
            del.style.opacity = '0.5';
            del.addEventListener('click', async () => {
                const result = await api('delete_honey_pot_msg', realIndex);
                if (result) renderHoneyPotMessages(result);
            });
            div.appendChild(del);
        }

        list.appendChild(div);
    });
}

async function addToHoneyPot() {
    const el = document.getElementById('new-todo');
    const html = el.innerHTML.trim();
    if (!html || html === '<br>') return;
    const text = htmlToMd(html);
    if (!text) return;

    const messages = await api('add_honey_pot_msg', text);
    if (messages) renderHoneyPotMessages(messages);
    el.innerHTML = '';
    el.focus();
}

// Called by file watcher when honey-pot.md changes externally
async function refreshHoneyPot() {
    if (!honeyPotMode || isEditingHoneyMsg) return;
    await loadHoneyPotMessages();
}

// ---- Manual refresh ----

async function manualRefresh() {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 400);

    if (honeyPotMode) {
        await loadHoneyPotMessages();
    } else {
        const data = await api('get_initial_data');
        if (data) {
            document.getElementById('streak-text').textContent = data.streak_display;
            document.getElementById('greeting-text').textContent = data.greeting;
            renderQuote(data.quote);
            renderTodos(data.items, true);
        }
    }
}

// ---- Settings panel ----

function toggleSettings() {
    settingsOpen = !settingsOpen;
    const panel = document.getElementById('settings-panel');
    if (settingsOpen) {
        panel.classList.add('open');
        loadSettingsValues();
    } else {
        panel.classList.remove('open');
    }
}

async function loadSettingsValues() {
    const settings = await api('get_settings');
    if (!settings) return;

    document.getElementById('setting-reminders').checked = settings.remindersEnabled;
    document.getElementById('setting-interval').value = String(settings.reminderInterval);
    document.getElementById('setting-opacity').value = settings.windowOpacity;
    document.getElementById('opacity-label').textContent = settings.windowOpacity + '%';
    document.getElementById('setting-show-input').checked = !inputCollapsed;
    document.getElementById('setting-show-quote').checked = !quoteCollapsed;
    document.getElementById('ui-font-label').textContent = uiFontSize + 'px';
    document.getElementById('todo-font-label').textContent = todoFontSize + 'px';
    document.getElementById('settings-info').textContent = 'Persona: ' + currentPersona;
}

async function updateSetting(key, value) {
    await api('update_setting', key, value);

    // Apply immediate side effects
    if (key === 'windowOpacity') {
        document.getElementById('opacity-label').textContent = value + '%';
        await api('set_window_opacity', value);
    }
}

async function resetSettings() {
    await api('reset_settings');
    // Reset local font sizes
    uiFontSize = 14;
    todoFontSize = 15;
    applyFontSizes();
    // Reset view toggles
    if (inputCollapsed) toggleInputArea();
    if (quoteCollapsed) toggleQuoteArea();
    // Reload panel values
    loadSettingsValues();
}

async function restartWidget() {
    await api('restart_widget');
}

async function closeWidget() {
    await api('close_widget');
}

// ---- Poem of the Day ----

let poemFontSize = 15;

function changePoemFontSize(delta) {
    poemFontSize = Math.max(11, Math.min(26, poemFontSize + delta));
    document.getElementById('poem-content').style.fontSize = poemFontSize + 'px';
}

async function togglePoemView() {
    poemViewOpen = !poemViewOpen;
    const overlay = document.getElementById('poem-overlay');
    const btn = document.getElementById('poem-btn');

    if (poemViewOpen) {
        overlay.classList.add('open');
        btn.classList.add('active');
        // Show loading, hide content
        document.getElementById('poem-loading').style.display = '';
        document.getElementById('poem-content').style.display = 'none';
        const poem = await api('get_poem_of_day');
        if (poem) {
            renderPoem(poem);
        } else {
            document.getElementById('poem-loading').textContent = 'could not fetch a poem right now...';
        }
    } else {
        overlay.classList.remove('open');
        btn.classList.remove('active');
    }
}

function renderPoem(poem) {
    document.getElementById('poem-loading').style.display = 'none';
    document.getElementById('poem-content').style.display = '';

    document.getElementById('poem-title').textContent = poem.title;
    document.getElementById('poem-author').textContent = poem.author;

    const linesEl = document.getElementById('poem-lines');
    linesEl.innerHTML = '';
    (poem.lines || []).forEach(line => {
        const p = document.createElement('p');
        p.textContent = line || '\u00A0';  // non-breaking space for blank lines
        linesEl.appendChild(p);
    });
}

// ---- Keyboard shortcuts ----

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && !e.shiftKey && !e.altKey) {
        if (e.key === 'z') { e.preventDefault(); undo(); return; }
        if (e.key === 'b') { e.preventDefault(); fmt('bold'); }
        if (e.key === 'i') { e.preventDefault(); fmt('italic'); }
        if (e.key === 'u') { e.preventDefault(); fmt('underline'); }
    }
});

document.getElementById('new-todo').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleAdd();
    }
    if (e.key === 'Tab') {
        e.preventDefault();
        if (e.shiftKey) {
            inputDepth = Math.max(0, inputDepth - 1);
        } else {
            inputDepth = inputDepth >= 3 ? 0 : inputDepth + 1;
        }
        updateInputDepthVisual();
    }
});

// ---- External file change refresh ----

async function refreshFromFile() {
    if (isRefreshing || honeyPotMode) return;
    // Skip refresh if user is editing a todo
    const active = document.activeElement;
    if (active && active.classList.contains('todo-text')) return;
    isRefreshing = true;
    try {
        const data = await api('get_initial_data');
        if (!data) return;
        document.getElementById('streak-text').textContent = data.streak_display;
        undoStack = []; // External changes invalidate undo history
        renderTodos(data.items, true);
    } finally {
        isRefreshing = false;
    }
}

// ---- Window position saving ----

let positionTimer = null;
window.addEventListener('resize', () => {
    clearTimeout(positionTimer);
    positionTimer = setTimeout(savePosition, 500);
});

function savePosition() {
    api('save_position', window.screenX, window.screenY, window.outerWidth, window.outerHeight);
}

// ---- Window resize handles ----

function setupResizeHandles() {
    const directions = ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'];
    const MIN_W = 280, MIN_H = 320;

    directions.forEach(dir => {
        const el = document.createElement('div');
        el.className = 'resize-handle resize-' + dir;
        document.body.appendChild(el);

        let startX, startY, startWinX, startWinY, startW, startH, rafId;
        const needsMove = dir.includes('n') || dir.includes('w');

        el.addEventListener('pointerdown', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            el.setPointerCapture(e.pointerId);
            startX = e.screenX;
            startY = e.screenY;
            // Use actual Win32 rect to avoid DPI mismatch
            const rect = await pywebview.api.get_window_rect();
            if (rect) {
                startWinX = rect.x;
                startWinY = rect.y;
                startW = rect.w;
                startH = rect.h;
            }
        });

        el.addEventListener('pointermove', (e) => {
            if (!el.hasPointerCapture(e.pointerId)) return;
            if (startW == null) return; // rect not yet loaded
            if (rafId) return; // throttle to one rAF at a time

            const sx = e.screenX, sy = e.screenY;
            rafId = requestAnimationFrame(() => {
                rafId = null;
                const dx = sx - startX;
                const dy = sy - startY;

                let x = startWinX, y = startWinY, w = startW, h = startH;

                if (dir.includes('e')) w = Math.max(MIN_W, startW + dx);
                if (dir.includes('w')) { w = Math.max(MIN_W, startW - dx); x = startWinX + startW - w; }
                if (dir.includes('s')) h = Math.max(MIN_H, startH + dy);
                if (dir.includes('n')) { h = Math.max(MIN_H, startH - dy); y = startWinY + startH - h; }

                if (needsMove) {
                    pywebview.api.move_and_resize(x, y, w, h);
                } else {
                    pywebview.api.resize_window(w, h);
                }
            });
        });

        el.addEventListener('pointerup', (e) => {
            if (el.hasPointerCapture(e.pointerId)) {
                el.releasePointerCapture(e.pointerId);
            }
            startW = null;
        });
    });
}

// ---- Start ----

window.addEventListener('pywebviewready', () => {
    setupResizeHandles();
    init();
});
