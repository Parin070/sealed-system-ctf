const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const sealIcon = document.querySelector('.seal-icon');

function createMessageElement(isUser) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isUser ? 'user-message' : 'system-message'}`;
    chatHistory.appendChild(msgDiv);
    return msgDiv;
}

function updateMessageContent(msgDiv, text, isUser) {
    if (!isUser && text.includes('iei{')) {
        const formattedText = text.replace(/(iei\{[^}]+\})/g, '<span class="flag-text">$1</span>');
        msgDiv.innerHTML = formattedText.replace(/\n/g, '<br>');
        sealIcon.classList.add('unlocked');
    } else {
        const escaped = text.replace(/&/g, "&amp;")
                            .replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;");
        msgDiv.innerHTML = escaped.replace(/\n/g, '<br>');
    }
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    
    userInput.value = '';
    
    const userMsgDiv = createMessageElement(true);
    updateMessageContent(userMsgDiv, text, true);
    
    sendButton.disabled = true;
    userInput.disabled = true;

    // Show thinking indicator
    const thinkingMsgDiv = createMessageElement(false);
    thinkingMsgDiv.classList.add('thinking-text');
    thinkingMsgDiv.innerHTML = "The seal stirs<span class='dots'>...</span>";
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ message: text })
        });
        
        if (!response.ok) {
            throw new Error('Network error');
        }

        // Remove thinking message completely, we will create a new one for the stream
        thinkingMsgDiv.remove();
        
        const systemMsgDiv = createMessageElement(false);
        let fullText = "";
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.slice(6);
                    if (dataStr === '[DONE]') {
                        continue;
                    }
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.chunk) {
                            fullText += data.chunk;
                            updateMessageContent(systemMsgDiv, fullText, false);
                        }
                    } catch (e) {
                        console.error("Error parsing SSE JSON", e, dataStr);
                    }
                }
            }
        }
        
    } catch (err) {
        console.error(err);
        thinkingMsgDiv.remove();
        const errorMsgDiv = createMessageElement(false);
        updateMessageContent(errorMsgDiv, "The seal remains silent... (Connection Error)", false);
    } finally {
        sendButton.disabled = false;
        userInput.disabled = false;
        userInput.focus();
    }
}

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
