const chatHistory = [];

document.getElementById('send-button').addEventListener('click', sendMessage);
document.getElementById('message-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
        sendButton.classList.remove('active');
    }
});

let svgContent = '';

// Fetch SVG content when the script loads
fetch('res/edge_logo.svg')
    .then(response => response.text())
    .then(data => {
        svgContent = data;
    })
    .catch(error => {
        console.error('Error loading SVG:', error);
    });

function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (message === '') return;

    addMessage('user-message', message);
    chatHistory.push({ role: 'user', content: message });
    input.value = '';

    // FIXME: Don't use hard-coded URL
    fetch('http://10.201.8.54:5000/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ messages: chatHistory })
    })
    .then(response => {
        if (response.headers.get('content-type')?.includes('application/json')) {
            // If the response is JSON, handle it as an error
            return response.json().then(data => {
                if (data.error) {
                    addMessage('bot-message', 'Error: ' + data.error);
                }
            });

        } else {
            // If the response is not JSON, handle it as a stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let receivedText = '';

            // Create a new message element for the streaming text
            const chatLog = document.getElementById('chat-log');
            const answer_div = document.createElement('div');
            answer_div.className = 'answer_div';
            const imgElement = document.createElement('div');
            imgElement.className = 'img_head';
            imgElement.innerHTML = svgContent;
            const messageElement = document.createElement('div');
            messageElement.className = 'message_from_llm';
            const messageContent = document.createElement('span');
            messageElement.appendChild(messageContent);
            answer_div.appendChild(imgElement)
            answer_div.appendChild(messageElement);
            chatLog.appendChild(answer_div);
            chatLog.scrollTop = chatLog.scrollHeight;

            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        // End of stream
                        if (receivedText) {
                            chatHistory.push({ role: 'assistant', content: receivedText });
                        }
                        return;
                    }
                    // Process the chunk of text
                    const chunk = decoder.decode(value, { stream: true });
                    receivedText += chunk;
                    messageContent.innerHTML = marked.parse(receivedText);
                    chatLog.scrollTop = chatLog.scrollHeight;
                    // Continue reading
                    readStream();
                }).catch(error => {
                    addMessage('bot-message', 'Error: ' + error.message);
                });
            }

            // Start reading the stream
            readStream();
        }
    })
    .catch(error => {
        addMessage('bot-message', 'Error: ' + error.message);
    });
}

function addMessage(className, message) {
    const chatLog = document.getElementById('chat-log');
    const messageElement = document.createElement('div');
    messageElement.className = 'message ' + className;
    messageElement.innerHTML = `<span>${message}</span>`;
    chatLog.appendChild(messageElement);
    chatLog.scrollTop = chatLog.scrollHeight;
}

// 动态更改发送按钮的颜色
document.getElementById('message-input').addEventListener('input', function() {
    const input = this.value.trim();
    const sendButton = document.getElementById('send-button');

    if (input.length > 0) {
        sendButton.classList.add('active');
    } else {
        sendButton.classList.remove('active');
    }
});