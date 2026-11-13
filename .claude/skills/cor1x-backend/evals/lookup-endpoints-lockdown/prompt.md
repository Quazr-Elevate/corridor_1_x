---
tags: [cor1x-backend, security, code]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

the pincode and ifsc lookup endpoints are wide open right now, anyone can hit them and burn through india post / razorpay through our server. lock them down — only signed in traders or admins, rate limit them, and cache the results for a day. add tests. give me the commit message you'd use too
