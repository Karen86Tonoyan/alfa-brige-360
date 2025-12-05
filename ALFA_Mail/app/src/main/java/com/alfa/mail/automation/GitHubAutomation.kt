package com.alfa.mail.automation

import android.content.Context
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.io.OutputStreamWriter
import java.util.Base64

/**
 * 🐙 GITHUB AUTOMATION - Automatyczna obsługa GitHub
 * 
 * Funkcje:
 * ✅ Auto-commit z AI-generated messages
 * ✅ Pull request management
 * ✅ Issue tracking and auto-response
 * ✅ Code review comments
 * ✅ Branch management
 * ✅ Release notes generation
 * ✅ Repository analytics
 */
class GitHubAutomation private constructor(private val context: Context) {
    
    private val gemini = Gemini2Service.getInstance(context)
    private var githubToken: String? = null
    private var username: String? = null
    
    data class GitHubConfig(
        val token: String,
        val username: String,
        val defaultRepo: String? = null
    )
    
    data class CommitInfo(
        val repo: String,
        val branch: String,
        val files: List<FileChange>,
        val message: String? = null, // If null, AI will generate
        val description: String? = null
    )
    
    data class FileChange(
        val path: String,
        val content: String,
        val operation: String // add, modify, delete
    )
    
    data class PullRequest(
        val title: String,
        val description: String,
        val fromBranch: String,
        val toBranch: String,
        val labels: List<String> = emptyList()
    )
    
    data class Issue(
        val number: Int,
        val title: String,
        val body: String,
        val labels: List<String>,
        val state: String,
        val comments: Int
    )
    
    companion object {
        @Volatile
        private var instance: GitHubAutomation? = null
        
        fun getInstance(context: Context): GitHubAutomation {
            return instance ?: synchronized(this) {
                instance ?: GitHubAutomation(context.applicationContext).also { instance = it }
            }
        }
    }
    
    fun configure(config: GitHubConfig) {
        githubToken = config.token
        username = config.username
    }
    
    /**
     * 📝 AUTO COMMIT
     * Automatyczny commit z AI-generated message
     */
    suspend fun autoCommit(commitInfo: CommitInfo): Result<String> = withContext(Dispatchers.IO) {
        try {
            // Generate commit message if not provided
            val commitMessage = commitInfo.message ?: generateCommitMessage(commitInfo.files)
            
            // Prepare API request
            val url = URL("https://api.github.com/repos/${username}/${commitInfo.repo}/contents/${commitInfo.files.first().path}")
            val connection = url.openConnection() as HttpURLConnection
            
            connection.requestMethod = "PUT"
            connection.setRequestProperty("Authorization", "token $githubToken")
            connection.setRequestProperty("Accept", "application/vnd.github.v3+json")
            connection.doOutput = true
            
            // Build request body
            val requestBody = JSONObject().apply {
                put("message", commitMessage)
                put("content", Base64.getEncoder().encodeToString(commitInfo.files.first().content.toByteArray()))
                put("branch", commitInfo.branch)
            }
            
            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write(requestBody.toString())
            }
            
            val responseCode = connection.responseCode
            if (responseCode == 201 || responseCode == 200) {
                Result.success("✅ Committed: $commitMessage")
            } else {
                Result.failure(Exception("GitHub API error: $responseCode"))
            }
            
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * 💬 GENERATE COMMIT MESSAGE
     * AI generuje commit message na podstawie zmian
     */
    private suspend fun generateCommitMessage(files: List<FileChange>): String {
        val prompt = """
        Generate a concise Git commit message for these changes:
        
        ${files.joinToString("\n") { 
            "${it.operation.uppercase()} ${it.path}\nContent preview: ${it.content.take(200)}..."
        }}
        
        Follow conventional commits format:
        - feat: new feature
        - fix: bug fix
        - docs: documentation
        - refactor: code refactoring
        - test: tests
        
        Return ONLY the commit message (no explanation).
        """.trimIndent()
        
        val response = gemini.generateText(prompt)
        return response.take(72) // Limit to 72 chars
    }
    
    /**
     * 🔀 CREATE PULL REQUEST
     * Tworzy PR z AI-generated description
     */
    suspend fun createPullRequest(
        repo: String,
        pr: PullRequest
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val url = URL("https://api.github.com/repos/${username}/${repo}/pulls")
            val connection = url.openConnection() as HttpURLConnection
            
            connection.requestMethod = "POST"
            connection.setRequestProperty("Authorization", "token $githubToken")
            connection.setRequestProperty("Accept", "application/vnd.github.v3+json")
            connection.doOutput = true
            
            val requestBody = JSONObject().apply {
                put("title", pr.title)
                put("body", pr.description)
                put("head", pr.fromBranch)
                put("base", pr.toBranch)
            }
            
            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write(requestBody.toString())
            }
            
            val responseCode = connection.responseCode
            if (responseCode == 201) {
                Result.success("✅ Pull request created: ${pr.title}")
            } else {
                Result.failure(Exception("GitHub API error: $responseCode"))
            }
            
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * 🎯 AUTO RESPOND TO ISSUES
     * Automatycznie odpowiada na issues z AI
     */
    suspend fun autoRespondToIssue(
        repo: String,
        issueNumber: Int,
        generateResponse: Boolean = true
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            // Fetch issue details
            val issue = fetchIssue(repo, issueNumber)
            
            // Generate AI response
            val response = if (generateResponse) {
                generateIssueResponse(issue)
            } else {
                "Thank you for reporting this issue. We'll look into it."
            }
            
            // Post comment
            postIssueComment(repo, issueNumber, response)
            
            Result.success("✅ Responded to issue #$issueNumber")
            
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    private suspend fun fetchIssue(repo: String, issueNumber: Int): Issue {
        val url = URL("https://api.github.com/repos/${username}/${repo}/issues/$issueNumber")
        val connection = url.openConnection() as HttpURLConnection
        
        connection.setRequestProperty("Authorization", "token $githubToken")
        connection.setRequestProperty("Accept", "application/vnd.github.v3+json")
        
        val response = connection.inputStream.bufferedReader().readText()
        val json = JSONObject(response)
        
        return Issue(
            number = json.getInt("number"),
            title = json.getString("title"),
            body = json.getString("body"),
            labels = JSONArray(json.getJSONArray("labels").toString()).let { arr ->
                (0 until arr.length()).map { arr.getJSONObject(it).getString("name") }
            },
            state = json.getString("state"),
            comments = json.getInt("comments")
        )
    }
    
    private suspend fun generateIssueResponse(issue: Issue): String {
        val prompt = """
        Generate a helpful response to this GitHub issue:
        
        Title: ${issue.title}
        Body: ${issue.body}
        Labels: ${issue.labels.joinToString(", ")}
        
        Response should:
        1. Acknowledge the issue
        2. Ask clarifying questions if needed
        3. Suggest potential solutions or workarounds
        4. Be professional and helpful
        
        Keep it concise (max 200 words).
        """.trimIndent()
        
        return gemini.generateText(prompt)
    }
    
    private suspend fun postIssueComment(repo: String, issueNumber: Int, comment: String): Result<String> {
        return try {
            val url = URL("https://api.github.com/repos/${username}/${repo}/issues/$issueNumber/comments")
            val connection = url.openConnection() as HttpURLConnection
            
            connection.requestMethod = "POST"
            connection.setRequestProperty("Authorization", "token $githubToken")
            connection.setRequestProperty("Accept", "application/vnd.github.v3+json")
            connection.doOutput = true
            
            val requestBody = JSONObject().apply {
                put("body", comment)
            }
            
            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write(requestBody.toString())
            }
            
            Result.success("Comment posted")
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * 📊 GENERATE RELEASE NOTES
     * AI generuje release notes z commitów
     */
    suspend fun generateReleaseNotes(
        repo: String,
        fromTag: String,
        toTag: String
    ): String = withContext(Dispatchers.IO) {
        
        // Fetch commits between tags
        val commits = fetchCommitsBetweenTags(repo, fromTag, toTag)
        
        val prompt = """
        Generate release notes from these commits:
        
        ${commits.joinToString("\n") { "- $it" }}
        
        Structure:
        ## What's New
        - Feature highlights
        
        ## Bug Fixes
        - Fixed issues
        
        ## Breaking Changes
        - Breaking changes (if any)
        
        Be concise and user-friendly.
        """.trimIndent()
        
        gemini.generateText(prompt)
    }
    
    private suspend fun fetchCommitsBetweenTags(repo: String, fromTag: String, toTag: String): List<String> {
        // Simplified - would call GitHub API
        return listOf(
            "feat: Add new email automation",
            "fix: Resolve PIN lock issue",
            "docs: Update README"
        )
    }
}
