const chatHistory = [];


document.getElementById('send-button').addEventListener('click', sendMessage);
document.getElementById('message-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

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

document.addEventListener('DOMContentLoaded', function() {
    const blocks = document.querySelectorAll('.block');
    const input = document.getElementById('message-input');

    blocks.forEach(block => {
        block.addEventListener('click', function() {
            // const content = block.getAttribute('data-content');
            // input.value = content;
            // sendMessage();
            replaceBlocks(block.id)
        });
    });
});

function replaceBlocks(block_id) {
    const useCaseDiv = document.getElementById('usecase-div');
    useCaseDiv.style.flexDirection = 'column';  // 设置为垂直排列
    useCaseDiv.style.gap = '10px';  // 设置子元素之间的间距
    // 删除现有的四个block
    useCaseDiv.innerHTML = '';

    let newBlocks = [];

    if (block_id === 'academic') {
        console.log(1111)
        newBlocks = [
            { id: 'block1', text: 'I am a freshman interested in majoring in computer science, please give me a course recommendation in the first session' },
            { id: 'block2', text: 'What’s EAP course in DKU?' },
            { id: 'block3', text: 'What are Common Core courses should I take?' },
            { id: 'block4', text: 'Introduce Credit/No Credit (CR/NC) grading system' }
        ];
    } else if (block_id === 'campus') {
        console.log(2222)
        newBlocks = [
            { id: 'block5', text: 'How to make a medical withdrawal from a course?' },
            { id: 'block6', text: 'When will students declare a major?' },
            { id: 'block7', text: 'Where can I ask for help if I have difficulties studying some courses?' },
            { id: 'block8', text: 'Who to contact when I have an emergency at DKU?' }
        ];
    } else if (block_id === 'service') {
        newBlocks = [
            { id: 'block9', text: 'How can I find an internship with the help of career services?' },
            { id: 'block11', text: 'What should I do if I have IT problem (in DKU)?' },
            { id: 'block10', text: 'How can I get help from Residence Life?' },
            { id: 'block12', text: 'What should I do if I have mental problems?' }
        ];
    } else if (block_id === 'tools') {
        newBlocks = [
            { id: 'block14', text: 'Could you please briefly generate an email to invite professor Bing Luo to have a lunch meeting with me?' },
            { id: 'block15', text: 'I am a rising Senior student. Please design a plan with timeline for my signature work to me.' },
            { id: 'block16', text: 'Show me the menu in DKU this week.' },
            { id: 'block17', text: 'How to organize my 7-week study plan for CS101 course.' }
        ];
    }
    

    newBlocks.forEach(blockInfo => {
        const block = document.createElement('div');
        
        block.classList.add('newblock');
        block.id = blockInfo.id;
        block.setAttribute('data-content', blockInfo.text);


        const text = document.createElement('div');
        text.classList.add('text');
        text.textContent = blockInfo.text;

        block.appendChild(text);

        block.addEventListener('click', function() {
            const content = block.getAttribute('data-content');
            document.getElementById('message-input').value = content;
            sendMessage();
        });

        useCaseDiv.appendChild(block);
        });

}


function sendMessage() {
    // 删除原decoration
    const page_center_logo = document.getElementById('page-center-logo-div');
    if (page_center_logo) {
        page_center_logo.remove();
    }
    const use_case = document.getElementById('usecase-div');
    if (use_case) {
        use_case.remove();
    }

    // 按钮变色
    const sendButton = document.getElementById('send-button');
    sendButton.classList.remove('active');

    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (message === '') return;

    addMessage('user-message', message);
    chatHistory.push({ role: 'user', content: message });
    input.value = '';

    // FIXME: Don't use hard-coded URL
    fetch('http://10.201.8.54:5001/chat', {
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
            imgElement.innerHTML = '<img src="res/DKU_LOGO.png" id="dku_logo" width="30px" alt="edge_lab_logo"></img>';
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

