import runpod


def handler(job):
    job_input = job["input"]
    return {"echo": job_input}


runpod.serverless.start({"handler": handler})
