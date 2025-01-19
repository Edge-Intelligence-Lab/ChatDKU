const chatHistory = [];


let globalChatHistoryId = 0;


function generateUniqueId() {
    return Date.now() + '-' + Math.random().toString(36).substring(2, 15);
}


fetch('http://10.200.14.82:9015/reset', {
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
        newBlocks = [
            { id: 'block1', text: 'What are the Distribution Requirements?' },
            { id: 'block2', text: 'What’s Common Core?' },
            { id: 'block3', text: 'Can I make changes to my course schedule after registration?' },
            { id: 'block4', text: 'How many credits can I take in a semester?' },
            { id: 'block5', text: 'Will courses that I withdrew show on my transcript?' },
            { id: 'block6', text: 'What letter grade would be considered CR and what would be considered NC?' },
            { id: 'block7', text: 'Can I repeat a course in which the grade of the record is CR/NC?' },
        ];
    }
    else if (block_id === 'campus') {
        newBlocks = [
            { id: 'block8', text: 'Can I change my declared major?' },
            { id: 'block9', text: 'What majors are available at Duke Kunshan University?' },
            { id: 'block10', text: 'Are there advisors who can guide me in selecting a major?' },
            { id: 'block11', text: 'Can I switch my major later on? How?' },
            { id: 'block12', text: 'What is the process for major declaration?' },
            { id: 'block13', text: 'When can I declare a major?' },
            { id: 'block14', text: 'What are the core courses required and electives of the Data Science major?' }
        ];
    }
    else if (block_id === 'service') {
        newBlocks = [
            { id: 'block15', text: 'Can I request a Leave of Absence for military service?' },
            { id: 'block16', text: 'How do I request a Medical Leave of Absence?' },
            { id: 'block17', text: 'What is considered an Academic Warning?' },
            { id: 'block18', text: 'How do I clear my probationary status?' },
            { id: 'block19', text: 'How many credits can I transfer from Study Abroad?' },
            { id: 'block20', text: 'What is the scoring standard for NSPHST and graduation requirement?' }
        ];
    }
    else if (block_id === 'tools') {
        newBlocks = [
            { id: 'block44', text: 'How can I get assistance from Residence Life?' },
            { id: 'block45', text: 'What should I do if I have an IT issue at DKU?' },
            { id: 'block46', text: 'What resources are available for mental health support at DKU?' },
            { id: 'block47', text: 'How can I find an internship with the help of DKU career services?' },
            { id: 'block48', text: 'What career services are offered, including resume workshops and job fairs?' },
            { id: 'block49', text: 'What scholarships and grants are available, and what are the eligibility criteria?' },
            { id: 'block50', text: 'What is the process for applying for financial aid?' },
            { id: 'block51', text: 'What are the resources for students interested in entrepreneurship?' },
            { id: 'block52', text: 'What student organizations and clubs are available?' },
            { id: 'block53', text: 'Are there work-study programs available, and how can students apply?' },
            { id: 'block54', text: 'Are there recreational and fitness facilities on campus?' },
            { id: 'block55', text: 'What are the rules regarding library rooms?' },
            { id: 'block56', text: 'What health services are provided on campus?' },
            { id: 'block57', text: 'Who should I contact in case of an emergency at DKU?' }
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
    let exsitingButton = document.getElementById('returnHomeButton')
    if(!exsitingButton){
        const returnHomeButton = document.createElement('button');
        returnHomeButton.textContent = "Return Home";
        returnHomeButton.id = 'returnHomeButton';
        returnHomeButton.style.position = 'fixed';
        returnHomeButton.style.display = 'flex';
        returnHomeButton.style.bottom = '60px';
        returnHomeButton.style.right = '30px';
        returnHomeButton.style.backgroundColor = 'transparent';
        returnHomeButton.style.color = 'grey'
        returnHomeButton.style.fontSize = '20px';
        returnHomeButton.style.fontFamily = 'serif';
        returnHomeButton.style.boxShadow = '2px 2px 5px rgba(0,0,0,0.3)';
        returnHomeButton.onclick = function() {
            window.location.href = 'http://chatdku.dukekunshan.edu.cn';  // 将此替换为您的初始网址
        };
        document.body.appendChild(returnHomeButton);
    }

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

    // 生成特定标识符
    globalChatHistoryId = generateUniqueId();

    // 将标识符添加到要发送给9015接口的请求数据中
    const requestData = {
        messages: chatHistory,
        chatHistoryId: globalChatHistoryId
    };

    // FIXME: Don't use hard-coded URL
    fetch('http://10.200.14.82:9015/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
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

function addMessage(className, message) {
    const chatLog = document.getElementById('chat-log');
    const messageElement = document.createElement('div');
    messageElement.className = 'message ' + className;
    messageElement.innerHTML = `<span>${message}</span>`;
    chatLog.appendChild(messageElement);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function askForFeedback(answer, userInput) {
    const chatLog = document.getElementById('chat-log');
    const feedbackDiv = document.createElement('div');
    feedbackDiv.id = 'feedbackDiv';

    const feedbackText = document.createElement('span');
    feedbackText.innerHTML = "Are you satisfied with the quality of the answers?";

    const yesButton = document.createElement('button');
    yesButton.textContent = 'Yes';
    yesButton.id = 'yesButton';
    yesButton.style.margin = '5px';
    yesButton.style.padding = '8px 16px';
    yesButton.style.border = 'none';
    yesButton.style.borderRadius = '4px';
    yesButton.style.cursor = 'pointer';
    yesButton.style.transition = 'background-color 0.3s';
    yesButton.style.color = 'white';
    yesButton.onclick = () => {
        feedbackDiv.remove();
    };


    const noButton = document.createElement('button');
    noButton.textContent = 'No';
    noButton.id = 'noButton';
    noButton.style.margin = '5px';
    noButton.style.padding = '8px 16px';
    noButton.style.border = 'none';
    noButton.style.borderRadius = '4px';
    noButton.style.cursor = 'pointer';
    noButton.style.transition = 'background-color 0.3s';
    noButton.style.color = 'white';
    noButton.onclick = () => {
        showFeedbackOptions(userInput, answer, feedbackDiv);
    };

    feedbackDiv.appendChild(feedbackText);
    feedbackDiv.appendChild(yesButton);
    feedbackDiv.appendChild(noButton);
    chatLog.appendChild(feedbackDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function showFeedbackOptions(userInput, answer, feedbackDiv) {
    const optionsDiv = document.createElement('div');
    optionsDiv.id = 'optionsDiv';

    const optionsText = document.createElement('span');
    optionsText.innerHTML = "Please select the reason for dissatisfaction:";

    const select = document.createElement('select');
    select.id = 'reasonSelect';
    const options = [
        "Outdated data",
        "Irrelevant answer",
        "False answer",
        "Others"
    ];
    options.forEach(option => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option;
        select.appendChild(opt);
    });

    const otherInput = document.createElement('input');
    otherInput.type = 'text';
    otherInput.id = 'otherInput';
    otherInput.placeholder = 'Please specify';

    select.onchange = () => {
        if (select.value === "Others") {
            otherInput.style.display = 'block';
        } else {
            otherInput.style.display = 'none';
        }
    };

    const submitButton = document.createElement('button');
    submitButton.textContent = 'Submit';
    submitButton.id = 'fbsubmitButton';
    submitButton.onclick = () => {
        const selectedReason = select.value === "Others" ? otherInput.value : select.value;
        saveFeedback(userInput, answer, selectedReason);
        feedbackDiv.remove();
        showApologyMessage(selectedReason);
    };

    optionsDiv.appendChild(optionsText);
    optionsDiv.appendChild(select);
    optionsDiv.appendChild(otherInput);
    optionsDiv.appendChild(submitButton);
    feedbackDiv.appendChild(optionsDiv);
}

function saveFeedback(input, answer, reason) {
    console.log("jrer")
    console.log(globalChatHistoryId)
    const data = {
        userInput: input,
        botAnswer: answer,
        feedbackReason: reason,
        chatHistoryId: globalChatHistoryId,
    };

    fetch('http://10.200.14.82:9016/save-feedback', {
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

function showApologyMessage(reason) {
    const chatLog = document.getElementById('chat-log');
    const apologyMessage = document.createElement('div');
    apologyMessage.className = 'apologyMessage';
    
    let messageText;
    switch (reason) {
        case "Outdated data":
            messageText = "We will update the database daily, if you are looking for the latest news, please wait for the update and try again!";
            break;
        case "Irrelevant answer":
            messageText = "Irrelevant responses may be due to the fact that the answers to relevant questions do not exist in the database, we will seek help from the relevant office to continuously expand our database!";
            break;
        case "False answer":
            messageText = "False answer may be due to the illusion effect of the large model, and we will continue to optimize our large model!";
            break;
        default:
            messageText = "Thank you for your feedback. We will use it to improve our service！";
    }
    messageText += "\n"
    messageText += "Tips for Better Answers: Try not to use abbreviations; Try to formulate the question logically."

    apologyMessage.innerHTML = messageText.replace(/\n/g, "<br>");
    chatLog.appendChild(apologyMessage);
    chatLog.scrollTop = chatLog.scrollHeight;
}


