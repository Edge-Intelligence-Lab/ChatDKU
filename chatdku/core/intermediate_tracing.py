class EventStream:

    def __init__(self, send, flush_size=10):
        self.send = send
        self.flush_size = flush_size
        self.chunk_buffer = []

    def reasoning(self, stage, content):
        self.send({
            "type": "reasoning",
            "stage": stage,
            "content": content
        })

    def chunk(self, content):
        self.chunk_buffer.append({
            "type": "chunk",
            "stage": "generation",
            "content": content
        })

        if len(self.chunk_buffer) >= self.flush_size:
            self.flush_chunks()

    def flush_chunks(self):
        if not self.chunk_buffer:
            return

        self.send({
            "type": "chunk_batch",
            "chunks": self.chunk_buffer
        })

        self.chunk_buffer = []

    def error(self, message):
        self.send({
            "type": "error",
            "stage": "error",
            "content": message
        })

    def end(self):
        self.flush_chunks()

        self.send({
            "type": "end",
            "stage": "end",
            "content": ""
        })