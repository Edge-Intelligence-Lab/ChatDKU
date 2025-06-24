export async function uploadFile(file: File) {
	// Option A – get presigned URL
	//   const { url, key } = await fetch("/api/presign?type="+file.type+"&ext="+
	//                                    file.name.split('.').pop())
	//                               .then(r => r.json());
	//   await fetch(url, { method: "PUT", body: file });   // bytes -> bucket

	// Option B – classic POST
	const fd = new FormData();
	fd.append("file", file);
	const { url: key } = await fetch("/api/upload", { method: "POST", body: fd }).then((r) => r.json());

	return key; // send this in your chat message
}
