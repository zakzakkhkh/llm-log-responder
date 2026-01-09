# User Study Template - LLM Log Responder System

## Instructions for System Administrators

This survey evaluates the usefulness and accuracy of the LLM-backed log summarization and alert responder system. Please review each scenario and rate the system's performance.

**Rating Scale:** 1 = Poor, 2 = Below Average, 3 = Average, 4 = Good, 5 = Excellent

---

## Scenario 1: Port Conflict Error

**Log Entry:**
```
2025-01-15 14:30:00 ERROR: Apache failed to start. Port 80 is in use.
```

**LLM Summary:**
```
Web server startup failure due to port conflict. The Apache service cannot start because port 80 is already occupied by another process.
```

**Suggested Action:** RESTART_APACHE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 2: Database Connection Timeout

**Log Entry:**
```
2025-01-15 14:35:00 CRITICAL: Database connection timeout after 30 seconds
```

**LLM Summary:**
```
Critical database connectivity issue. The system cannot establish a connection to the database server, indicating potential network or service problems.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 3: Permission Denied Error

**Log Entry:**
```
2025-01-15 14:40:00 ERROR: Permission denied: cannot write to /var/log/app.log
```

**LLM Summary:**
```
File system permission error. The application lacks write permissions for the log file directory.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 4: Disk Space Warning

**Log Entry:**
```
2025-01-15 14:45:00 CRITICAL: Disk space below 5% threshold on /var
```

**LLM Summary:**
```
Critical disk space alert. The /var partition has less than 5% free space remaining, requiring immediate attention.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 5: Service Restart Failure

**Log Entry:**
```
2025-01-15 14:50:00 ERROR: Service nginx failed to restart
```

**LLM Summary:**
```
Service restart failure. The nginx web server service failed to restart, indicating a configuration or dependency issue.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 6: Memory Usage Alert

**Log Entry:**
```
2025-01-15 14:55:00 CRITICAL: Memory usage exceeded 95% threshold
```

**LLM Summary:**
```
Critical memory pressure. System memory usage has exceeded 95%, potentially causing performance degradation or service failures.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 7: SSL Certificate Expiration

**Log Entry:**
```
2025-01-15 15:00:00 ERROR: SSL certificate expired for domain example.com
```

**LLM Summary:**
```
SSL certificate expiration. The SSL certificate for example.com has expired, requiring certificate renewal to maintain secure connections.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Scenario 8: Authentication Failure

**Log Entry:**
```
2025-01-15 15:05:00 ERROR: Failed to authenticate user: invalid credentials
```

**LLM Summary:**
```
Authentication failure. User login attempt failed due to invalid credentials, which could indicate a typo or potential security concern.
```

**Suggested Action:** ESCALATE

**Questions:**
1. How accurate is this summary? (1-5): ___
2. How useful is the suggested action? (1-5): ___
3. Would you trust this system in production? (1-5): ___
4. How clear is the explanation? (1-5): ___

**Comments:**
___
___

---

## Overall Assessment

**General Questions:**
1. Overall, how useful would this system be in your daily operations? (1-5): ___
2. How likely are you to adopt this system? (1-5): ___
3. What improvements would you suggest?
___
___
___

4. What features are most valuable to you?
___
___
___

5. What concerns do you have about using this system?
___
___
___

---

## Scoring Guide

After collecting responses, calculate:
- **Average Summary Accuracy:** Sum of all Q1 scores / number of scenarios
- **Average Action Usefulness:** Sum of all Q2 scores / number of scenarios
- **Average Trust Score:** Sum of all Q3 scores / number of scenarios
- **Average Clarity Score:** Sum of all Q4 scores / number of scenarios
- **Overall Usefulness:** Q1 from Overall Assessment
- **Adoption Likelihood:** Q2 from Overall Assessment

**Interpretation:**
- 4.0-5.0: Excellent - System is highly useful
- 3.0-3.9: Good - System is useful with minor improvements
- 2.0-2.9: Average - System needs significant improvements
- 1.0-1.9: Poor - System is not useful

---

**Thank you for your participation!**
