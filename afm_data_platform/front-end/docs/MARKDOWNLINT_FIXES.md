# Markdownlint Compliance Guide

This document outlines the markdownlint violations found in the tutorial files and provides specific fixes based on the official markdownlint rules from https://github.com/DavidAnson/markdownlint/tree/v0.38.0/doc.

## Summary of Issues

### ✅ FIXED
- **glossary.md**: All 24 MD036 violations fixed
- **README.md**: Clean, no violations
- **claude.md**: Clean, no violations

### 🚨 NEEDS FIXING
All tutorial files in `/tutorials/` have extensive MD036 violations.

## MD036 Rule Explanation

**Rule**: Emphasis used instead of a heading  
**Official Documentation**: https://github.com/DavidAnson/markdownlint/blob/v0.38.0/doc/md036.md

**What it catches**: Single-line paragraphs that are entirely emphasized text (bold `**text**` or italic `*text*`) when they should be proper headings.

**Why it matters**: Using emphasis instead of headings prevents tools from inferring document structure.

## Tutorial Files That Need Fixing

### Critical Pattern to Fix

**❌ WRONG (MD036 Violation):**
```markdown
# **시작하기 전에**
## **가이드 목적**
### **🎯 Node.js가 Vue 개발에 필요한 이유**
```

**✅ CORRECT:**
```markdown
# 시작하기 전에
## 가이드 목적
### 🎯 Node.js가 Vue 개발에 필요한 이유
```

## Specific Files and Violations

### Chapter 1_시작하기 전에.md
**MD036 Violations to Fix:**
- Line 1: `# **시작하기 전에**` → `# 시작하기 전에`
- Line 3: `## **가이드 목적**` → `## 가이드 목적`
- Line 9: `## **대상 독자**` → `## 대상 독자`
- Additional violations throughout file

**MD022 Violations:**
- Missing blank lines around some headings

### Chapter 2_개발 환경 구축하기.md
**MD036 Violations to Fix:**
- Line 1: `# **🛠️ Node.js 설치 및 Vue 개발 환경 구축**` → `# 🛠️ Node.js 설치 및 Vue 개발 환경 구축`
- Line 3: `## **🤔 Node.js란 무엇인가?**` → `## 🤔 Node.js란 무엇인가?`
- Line 13: `### **🎯 Node.js가 Vue 개발에 필요한 이유**` → `### 🎯 Node.js가 Vue 개발에 필요한 이유`
- Line 24: `## **💻 Node.js 설치하기**` → `## 💻 Node.js 설치하기`
- Extensive violations throughout file

### Chapter 3_Vue 프로젝트 시작하기.md
**MD036 Violations to Fix:**
- Line 1: `# **🎯 Vue 프로젝트 시작하기**` → `# 🎯 Vue 프로젝트 시작하기`
- Line 3: `## **🚀 Vue.js 프레임워크 이해하기**` → `## 🚀 Vue.js 프레임워크 이해하기`
- Line 5: `### **🤔 Vue.js란 무엇인가?**` → `### 🤔 Vue.js란 무엇인가?`
- Extensive violations throughout file

### Chapter 4_1_Vue3 기초 다지기.md
**MD036 Violations to Fix:**
- Line 1: `# **Vue 3 기초 다지기**` → `# Vue 3 기초 다지기`
- Line 8: `## **컴포넌트의 개념**` → `## 컴포넌트의 개념`
- Line 23: `## **템플릿 문법**` → `## 템플릿 문법`
- Line 79: `## **반응성 시스템**` → `## 반응성 시스템`
- Multiple violations throughout file

### Chapter 4_2_Vue3 좀 더 다지기.md
- Similar extensive MD036 violations throughout file

### All Other Tutorial Chapters
- Chapters 5-12 all follow the same pattern of wrapping headings in `**bold**` formatting
- Each requires systematic removal of `**` from headings

## Automated Fix Strategy

### Find and Replace Pattern

You can use a global find-and-replace in your editor:

**Find (using regex):**
```regex
^(#{1,6})\s+\*\*(.*?)\*\*\s*$
```

**Replace:**
```regex
$1 $2
```

This will find all lines that:
- Start with 1-6 hash marks (`#`, `##`, etc.)
- Have bold formatting around the heading text
- Replace with proper heading without bold formatting

### Manual Verification Needed

After automated replacement:
1. Check that emojis and special characters are preserved
2. Ensure no accidental changes to non-heading bold text
3. Verify heading hierarchy remains correct

## Additional Markdownlint Rules to Consider

### MD022: Headings should be surrounded by blank lines
Some files have headings without proper spacing.

**Fix**: Add blank lines before and after headings.

### MD013: Line length
Some files have very long lines.

**Fix**: Consider breaking long lines at around 80-120 characters.

### MD012: No multiple consecutive blank lines
**Fix**: Remove extra blank lines (keep only one).

## Testing Compliance

After fixes, you can test with:
```bash
# Install markdownlint-cli
npm install -g markdownlint-cli

# Test specific file
markdownlint front-end/docs/tutorials/Chapter\ 1_시작하기\ 전에.md

# Test all tutorial files
markdownlint front-end/docs/tutorials/*.md
```

## Priority Order

1. **High Priority**: Fix all MD036 violations (heading emphasis)
2. **Medium Priority**: Fix MD022 violations (blank lines around headings)
3. **Low Priority**: Consider MD013 (line length) improvements

## Status

- ✅ **glossary.md**: Fixed (24 MD036 violations corrected)
- 🚨 **Tutorial files**: Awaiting systematic fix of MD036 violations
- ✅ **README.md**: Clean
- ✅ **claude.md**: Clean

The tutorial files follow a consistent pattern, making them good candidates for automated find-and-replace operations.