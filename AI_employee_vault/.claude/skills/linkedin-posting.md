# Skill: LinkedIn Auto-Posting

## Purpose
Post business content to LinkedIn automatically after human approval.

## Trigger
File in Approved/ with frontmatter: post_linkedin: true

## Workflow
1. Human places post file in Approved/
2. linkedin_poster.py detects it
3. Extracts content under "## Post Content" section
4. Posts via LinkedIn UGC API
5. Moves file to Done/
6. Logs to Logs/linkedin.log

## File Format Required
---
type: linkedin
post_linkedin: true
---
## Post Content
Your post text here.
