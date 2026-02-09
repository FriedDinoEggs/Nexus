import './style.css'

let client = null;

const googleLoginBtn = document.getElementById('googleLoginBtn');
const clientIdInput = document.getElementById('clientIdInput');
const statusBar = document.getElementById('statusBar');

// Auto-fill Client ID if available in environment variables
if (import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID) {
    clientIdInput.value = import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID;
}

const statusText = document.getElementById('statusText');
const codeSection = document.getElementById('codeSection');
const authCode = document.getElementById('authCode');
const copyBtn = document.getElementById('copyBtn');
const backendLoginBtn = document.getElementById('backendLoginBtn');

const tokenSection = document.getElementById('tokenSection');
const accessToken = document.getElementById('accessToken');
const refreshToken = document.getElementById('refreshToken');

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

// 通用複製函數
function copyToClipboard(element, originalColor) {
    const text = element.textContent;
    if (!text || text === 'N/A') return;

    navigator.clipboard.writeText(text).then(() => {
        const parent = element.parentElement;
        const originalBg = parent.style.background;
        parent.style.background = 'rgba(255, 255, 255, 0.2)';
        setTimeout(() => {
            parent.style.background = originalBg;
        }, 200);
    });
}

// 點擊區塊複製
document.getElementById('copyCodeBlock').addEventListener('click', function() {
    copyToClipboard(authCode);
});

document.getElementById('accessTokenBlock').addEventListener('click', function() {
    copyToClipboard(accessToken);
});

document.getElementById('refreshTokenBlock').addEventListener('click', function() {
    copyToClipboard(refreshToken);
});

backendLoginBtn.addEventListener('click', async () => {
    const code = authCode.textContent;
    if (!code) return;

    setStatus('pending', '正在嘗試登入後端...');
    
    try {
        const response = await fetch('/api/v1/users/login/google/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code: code }),
        });

        const data = await response.json();

        if (response.ok) {
            console.log('Backend Login Success:', data);
            setStatus('success', '後端登入成功！');
            
            // 顯示 Token 區塊並填入數值
            tokenSection.style.display = 'block';
            accessToken.textContent = data.access_token || data.access || 'N/A';
            refreshToken.textContent = data.refresh_token || data.refresh || 'N/A';
            
            alert('登入成功！Token 已顯示在下方，點擊區塊即可複製。');
        } else {
            console.error('Backend Login Failed:', data);
            setStatus('error', `後端登入失敗: ${data.detail || response.statusText}`);
        }
    } catch (error) {
        console.error('Network Error:', error);
        setStatus('error', `連線失敗: ${error.message}`);
    }
});