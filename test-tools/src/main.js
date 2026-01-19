import './style.css'

let client = null;

const googleLoginBtn = document.getElementById('googleLoginBtn');
const clientIdInput = document.getElementById('clientIdInput');
const statusBar = document.getElementById('statusBar');
const statusText = document.getElementById('statusText');
const codeSection = document.getElementById('codeSection');
const authCode = document.getElementById('authCode');
const copyBtn = document.getElementById('copyBtn');

function setStatus(type, message) {
    statusBar.className = 'status ' + type;
    statusText.textContent = message;
}

function handleCodeResponse(response) {
    console.log('Google Response:', response);

    if (response.error) {
        setStatus('error', `發生錯誤: ${response.error}`);
        return;
    }

    if (response.code) {
        codeSection.style.display = 'block';
        authCode.textContent = response.code;
        setStatus('success', '成功獲取 Authorization Code！');
    }
}

googleLoginBtn.addEventListener('click', () => {
    const clientId = clientIdInput.value.trim();
    
    if (!clientId) {
        alert('請先輸入 Google Client ID');
        return;
    }

    if (typeof google === 'undefined') {
        alert('Google GIS SDK 尚未載入，請稍候或檢查網路連線');
        return;
    }

    try {
        // 初始化 GIS Code Client
        client = google.accounts.oauth2.initCodeClient({
            client_id: clientId,
            scope: 'openid profile email',
            ux_mode: 'popup',
            callback: handleCodeResponse,
        });

        setStatus('pending', '正在開啟 Google 授權視窗...');
        client.requestCode();
    } catch (error) {
        console.error('Initialization Error:', error);
        setStatus('error', `初始化失敗: ${error.message}`);
    }
});

copyBtn.addEventListener('click', () => {
    const code = authCode.textContent;
    navigator.clipboard.writeText(code).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = '✅ 已複製！';
        setTimeout(() => {
            copyBtn.textContent = originalText;
        }, 2000);
    });
});