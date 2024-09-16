const chatHistory = [];

fetch('http://10.200.14.82:5002/reset', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
})
.then(console.log("reset agent"))


document.getElementById('send-button').addEventListener('click', sendMessage);
document.getElementById('message-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

chatdku_remarks = document.getElementById('about-chatdku')

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
    chatdku_remarks.remove()

    let newBlocks = [];
    
    if (block_id === 'academic') {
        console.log(1111)
        newBlocks = [
            { id: 'block1', text: 'I am a freshman interested in majoring in computer science, please give me a course recommendation in the first session.' },
            { id: 'block2', text: 'Introduce Credit/No Credit (CR/NC) grading system.' },
            { id: 'block3', text: 'What are Common Core courses should I take?' },
            { id: 'block4', text: 'What’s EAP course at DKU?' },
            { id: 'block5', text: 'Do you know the Guidelines for Appointment of Adjunct Faculty?'}
        ];
    } else if (block_id === 'campus') {
        newBlocks = [
            { id: 'block6', text: 'How to make a medical withdrawal from a course?' },
            { id: 'block7', text: 'When will students declare a major?' },
            { id: 'block8', text: 'Where can I ask for help if I have difficulties studying some course?' },
            { id: 'block9', text: 'Who to contact when I have an emergency at DKU?' }
        ];
    } else if (block_id === 'service') {
        newBlocks = [
            { id: 'block11', text: 'How can I get help from Residence Life?' },
            { id: 'block12', text: 'What should I do if I have IT problem (in DKU)?' },
            { id: 'block13', text: 'What should I do if I have some mental problem (in DKU)?' },
            { id: 'block14', text: 'How can I find an internship with the help of career services in DKU?' }
        ];
    } else if (block_id === 'tools') {
        newBlocks = [
            { id: 'block16', text: 'Please reserve a big meeting room in IB building.' },
            { id: 'block17', text: 'Could you please briefly generate an email to invite professor Bing Luo to have a lunch meeting with me?' },
            { id: 'block18', text: 'I am a rising Senior student. Please design a plan with timeline for my signature work to me.' },
            { id: 'block19', text: 'Show me the menu in DKU this week.' },
            { id: 'block20', text: 'How to organize my 7-week study plan for CS101 course.' }
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

         // 添加返回按钮
         const backButton = document.createElement('div');
         backButton.classList.add('newblock'); // 使用相同的类名以应用样式
         backButton.textContent = '🔙';
         backButton.style.fontSize = '25px';
         backButton.style.cursor = 'pointer'; // 鼠标悬停时显示为指针
         backButton.style.width = '30px'; // 设置宽度
         backButton.style.height = '30px'; // 设置高度
         backButton.style.border = '10px solid transparent'; // 设置边框
         backButton.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)'; // 设置阴影
         backButton.style.borderRadius = '10px'; // 设置圆角
         backButton.style.overflow = 'hidden'; // 溢出隐藏
         backButton.style.marginTop = '2%'; // 设置与上方元素的间距
         backButton.style.display = 'flex'; // 使用flex布局
         backButton.style.alignItems = 'center'; // 垂直居中
         backButton.style.justifyContent = 'center'; // 水平居中
         backButton.style.color = 'black'; // 字体颜
         backButton.style.transition = 'background-color 0.3s'; // 动画效果
     
         // 悬停效果
         backButton.addEventListener('mouseover', function() {
             backButton.style.backgroundColor = '#0056b3'; // 悬停时的背景颜色
         });
     
         backButton.addEventListener('mouseout', function() {
             backButton.style.backgroundColor = 'white'; // 恢复背景颜色
         });
     
         backButton.addEventListener('click', function() {
             window.location.href = 'http://chatdku.dukekunshan.edu.cn/'; // 跳转到指定网页
         });
     
         useCaseDiv.appendChild(backButton);
     

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
    chatdku_remarks.remove()

    // 按钮变色
    const sendButton = document.getElementById('send-button');
    sendButton.classList.remove('active');

    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (message === '') return;

    addMessage('user-message', message);
    chatHistory.push({ role: 'user', content: message });
    input.value = '';

    // Disable the send button
    input.disabled = true;
    sendButton.disabled = true;

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

    // 创建并显示加载动画
    const loader = document.createElement('div');
    const loading_txt = document.createElement('span');
    loading_txt.innerHTML = "Searching relevant documents for you, this can take several seconds.."
    loader.className = 'loader'; // 添加CSS类以样式化加载动画
    messageElement.appendChild(loading_txt);
    messageElement.appendChild(loader); // 将loader添加到messageElement中
    chatLog.scrollTop = chatLog.scrollHeight;


    // FIXME: Don't use hard-coded URL
    fetch('http://10.200.14.82:5002/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ messages: chatHistory })
    })
    .then(response => {
        // 接收到响应后隐藏加载动画
        loader.remove();
        loading_txt.remove();
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


            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        // End of stream
                        if (receivedText) {
                            chatHistory.push({ role: 'assistant', content: receivedText });

                            messageContent.innerHTML = marked.parse(receivedText);
                            chatLog.scrollTop = chatLog.scrollHeight;

                            // 询问用户对回答的质量是否满意
                            askForFeedback(receivedText, message);
                        }
                        sendButton.disabled = false;
                        input.disabled = false;
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
                    input.disabled = false;
                    sendButton.disabled = false;
                });
            }

            // Start reading the stream
            readStream();
        }
    })
    .catch(error => {
        addMessage('bot-message', 'Error: ' + error.message);
        input.disabled = false;
        sendButton.disabled = false;

    });
}

function askForFeedback(answer, userInput) {
    const chatLog = document.getElementById('chat-log');
    const feedbackDiv = document.createElement('div');
    feedbackDiv.className = 'feedback_div';

    const feedbackText = document.createElement('span');
    feedbackText.innerHTML = "Are you satisfied with the quality of the answers?";

    const yesButton = document.createElement('button');
    yesButton.textContent = 'Yes';
    yesButton.className = 'feedback-button yes-button'; // 添加类名
    yesButton.onclick = () => {
        feedbackDiv.remove(); // 移除反馈部分
    };

    const noButton = document.createElement('button');
    noButton.textContent = 'No!!!';
    noButton.className = 'feedback-button no-button'; // 添加类名
    noButton.onclick = () => {
        // 存储用户输入和对应的答案
        saveFeedback(userInput, answer);
        feedbackDiv.remove(); // 移除反馈部分
    };

    feedbackDiv.appendChild(feedbackText);
    feedbackDiv.appendChild(yesButton);
    feedbackDiv.appendChild(noButton);
    chatLog.appendChild(feedbackDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
}


function saveFeedback(input, answer) {
    const data = {
        userInput: input,
        botAnswer: answer
    };

    fetch('http://10.200.14.82:5003/save-feedback', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        console.log('Feedback saved successfully');
    })
    .catch(error => {
        console.error('There was a problem with the fetch operation:', error);
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
