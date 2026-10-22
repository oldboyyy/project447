const $ = (id) => document.getElementById(id);
let attendance = [];
let busy = false;
let stream = null;
let timer = null;
let cameraVersion = 0;
let activeVideo = null;
let hasSamples = false;
let currentPage = '';
const pages = {
    dashboard: ['Automatic attendance', 'Recognize faces and keep your class attendance in one place.'],
    upload: ['Upload photo', 'Turn a classroom photo into an attendance list.'],
    camera: ['Live camera', 'Recognize students directly from your camera.'],
    attendance: ['Attendance', 'Review and export the results of your latest scan.'],
    settings: ['Settings', 'View the current recognition configuration.'],
    help: ['Help center', 'Everything you need to take your first attendance.'],
};

function navigate() {
    const requested = location.hash.slice(1) || 'dashboard';
    const page = Object.hasOwn(pages, requested) ? requested : 'dashboard';
    if (currentPage === 'camera' && page !== 'camera') stopCamera();
    document.querySelectorAll('[data-page]').forEach(section => {
        section.hidden = section.dataset.page !== page;
    });
    document.querySelectorAll('.nav-link').forEach(link => {
        const active = link.hash === `#${page}`;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });
    $('page-title').textContent = pages[page][0];
    $('page-description').textContent = pages[page][1];
    document.title = `${page === 'dashboard' ? 'Dashboard' : pages[page][0]} · SDU Attendance`;
    $('recognition-feedback').hidden = !['upload', 'camera'].includes(page);
    currentPage = page;
}

$('today-date').textContent = new Intl.DateTimeFormat('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
}).format(new Date());
window.addEventListener('hashchange', navigate);
navigate();

function message(text, error = false) {
    $('message').textContent = text;
    $('message').style.color = error ? '#b42318' : '#334155';
}

function showResults(data) {
    attendance = data.attendance;
    const body = document.querySelector('#attendance-table tbody');
    body.replaceChildren();
    [...attendance].sort((a, b) => Number(b.present) - Number(a.present)).forEach(student => {
        const row = body.insertRow();
        row.insertCell().textContent = student.id || '—';
        row.insertCell().textContent = student.name;
        const status = row.insertCell();
        status.textContent = student.present ? '✓ Present' : '— Not detected';
        status.className = student.present ? 'present' : 'not-detected';
    });
    const present = attendance.filter(student => student.present);
    $('summary').textContent = `${present.length} of ${attendance.length} students recognized · ${data.detected} faces · личность не подтверждена: ${data.unknown}`;
    updateDashboard(data, present);
    $('detected-names').textContent = present.map(student => student.name).join(', ') || 'No enrolled students recognized';
    $('result-image').src = data.image;
    $('result-image').hidden = false;
    $('export-csv').disabled = false;
    $('result-list-link').hidden = false;
    message(data.detected ? 'Recognition complete. Results reflect the latest frame.' : 'No faces found. Try a clearer, front-facing photo.');
}

function updateDashboard(data, present) {
    const now = new Date();
    const time = now.toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'});
    const rate = attendance.length ? Math.round(present.length / attendance.length * 100) : 0;
    $('recognized-count').textContent = present.length;
    $('recognized-note').textContent = `личность не подтверждена: ${data.unknown}`;
    $('recognized-note').classList.add('has-results');
    $('attendance-rate').textContent = `${rate}%`;
    $('rate-note').textContent = 'In the latest scan';
    $('rate-note').classList.add('has-results');
    $('present-total').textContent = `${present.length} / ${attendance.length}`;
    $('attendance-progress').value = rate;
    $('last-scan').textContent = time;
    $('last-scan').dateTime = now.toISOString();
    $('latest-caption').textContent = `${now.toLocaleDateString('en-US', {month: 'long', day: 'numeric'})} · ${data.detected} ${data.detected === 1 ? 'face' : 'faces'} detected`;
    const results = $('latest-results');
    results.replaceChildren();
    if (!data.faces.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-state';
        empty.textContent = 'No faces detected in the latest scan. Try another photo.';
        results.append(empty);
    }
    data.faces.forEach(face => {
        const row = document.createElement('div');
        row.className = `recognition-row${face.name ? '' : ' unknown'}`;
        const icon = document.createElement('span');
        icon.className = 'recognition-icon';
        icon.textContent = face.name ? '✓' : '?';
        icon.setAttribute('aria-hidden', 'true');
        const content = document.createElement('div');
        const name = document.createElement('p');
        name.className = 'recognition-name';
        name.textContent = face.name || 'личность не подтверждена';
        const info = document.createElement('p');
        info.className = 'recognition-info';
        info.textContent = face.name ? 'Present · recognized in last scan' : 'Требуется проверка';
        const timestamp = document.createElement('time');
        timestamp.dateTime = now.toISOString();
        timestamp.textContent = time;
        content.append(name, info);
        row.append(icon, content, timestamp);
        results.append(row);
    });
}

async function recognize(blob, name = 'photo.jpg') {
    if (busy) return;
    busy = true;
    $('upload-form').setAttribute('aria-busy', 'true');
    const submit = document.querySelector('#upload-form button');
    submit.disabled = true;
    $('run-sample').disabled = true;
    message('Recognizing faces…');
    try {
        const form = new FormData();
        form.append('photo', blob, name);
        const response = await fetch('/upload', {method: 'POST', body: form});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'The server could not process this image.');
        showResults(data);
    } catch (error) {
        message(error.message, true);
    } finally {
        busy = false;
        $('upload-form').removeAttribute('aria-busy');
        submit.disabled = false;
        $('run-sample').disabled = !hasSamples;
    }
}

$('upload-form').addEventListener('submit', event => {
    event.preventDefault();
    const file = $('photo').files[0];
    if (file) recognize(file, file.name);
});

$('run-sample').addEventListener('click', async () => {
    if (busy || !hasSamples) return;
    $('run-sample').disabled = true;
    try {
        const response = await fetch(`/api/samples/${$('sample-select').value}`);
        if (!response.ok) throw new Error('Could not load this sample.');
        await recognize(await response.blob(), 'sample.jpg');
    } catch (error) { message(error.message, true); }
    finally { $('run-sample').disabled = busy || !hasSamples; }
});

function stopCamera() {
    cameraVersion++;
    clearTimeout(timer);
    timer = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    activeVideo = null;
    $('camera-preview').srcObject = null;
    $('real-time-preview').srcObject = null;
    $('start-camera').disabled = false;
    $('start-real-time').disabled = false;
    $('stop-camera').disabled = true;
    $('stop-real-time').disabled = true;
    $('take-picture').disabled = true;
}

async function capture(video) {
    if (!video.videoWidth || !video.videoHeight || busy) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    if (blob) await recognize(blob, 'camera.jpg');
}

async function startCamera(realtime) {
    stopCamera();
    const version = cameraVersion;
    $('start-camera').disabled = true;
    $('start-real-time').disabled = true;
    try {
        const camera = await navigator.mediaDevices.getUserMedia({video: true, audio: false});
        if (version !== cameraVersion) {
            camera.getTracks().forEach(track => track.stop());
            return;
        }
        stream = camera;
        activeVideo = realtime ? $('real-time-preview') : $('camera-preview');
        activeVideo.srcObject = stream;
        await activeVideo.play();
        if (version !== cameraVersion) return;
        $('stop-camera').disabled = false;
        $('stop-real-time').disabled = !realtime;
        $('take-picture').disabled = realtime;
        if (realtime) {
            const tick = async () => {
                if (version !== cameraVersion) return;
                await capture($('real-time-preview'));
                if (version === cameraVersion) timer = setTimeout(tick, 3000);
            };
            await tick();
        }
    } catch (error) {
        if (version !== cameraVersion) return;
        stopCamera();
        message('Could not start the camera. Allow camera access in your browser or upload a photo.', true);
    }
}

$('start-camera').addEventListener('click', () => startCamera(false));
$('start-real-time').addEventListener('click', () => startCamera(true));
$('stop-camera').addEventListener('click', stopCamera);
$('stop-real-time').addEventListener('click', stopCamera);
$('take-picture').addEventListener('click', () => capture($('camera-preview')));
window.addEventListener('pagehide', stopCamera);

$('export-csv').addEventListener('click', () => {
    const escape = value => '"' + String(value).replaceAll('"', '""') + '"';
    const csv = '\uFEFFID,Name,Status\r\n' + attendance.map(s => `${escape(s.id || '')},${escape(s.name)},${s.present ? 'Present' : 'Not detected'}`).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'attendance.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
});

fetch('/api/status').then(async response => {
    if (!response.ok) throw new Error('The recognition model is unavailable.');
    return response.json();
}).then(data => {
    $('model-status').textContent = 'Ready';
    $('status-dot').className = 'status-dot ready';
    $('model-detail').textContent = `dlib · tolerance ${data.tolerance}`;
    $('model-caption').textContent = `Local model · ${data.students} students`;
    $('setting-tolerance').textContent = data.tolerance;
    $('setting-students').textContent = data.students;
    if (!attendance.length) $('present-total').textContent = `— / ${data.students}`;
    hasSamples = data.samples.length > 0;
    $('sample-select').replaceChildren();
    data.samples.forEach(sample => $('sample-select').add(new Option(sample.name, sample.id)));
    if (!hasSamples) $('sample-select').add(new Option('No samples available', ''));
    $('sample-select').disabled = !hasSamples;
    $('run-sample').disabled = busy || !hasSamples;
}).catch(error => {
    $('model-status').textContent = 'Unavailable';
    $('status-dot').className = 'status-dot error';
    $('model-detail').textContent = 'Check the local server';
    $('model-caption').textContent = 'Model unavailable';
    $('sample-select').replaceChildren(new Option('Samples unavailable', ''));
    $('sample-select').disabled = true;
    message(error.message, true);
});
