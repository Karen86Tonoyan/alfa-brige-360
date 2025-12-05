package com.alfa.mail.automation

import android.content.Context
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * 🐍 PYTHON IN CHAT - Wykonywanie Python w czasie rzeczywistym w chacie
 * 
 * Funkcje:
 * ✅ Uruchamianie Python code z chatu
 * ✅ Data analysis na żywo
 * ✅ Plotting i wizualizacje
 * ✅ Machine learning inference
 * ✅ API calls z Python
 * ✅ File processing
 * ✅ Real-time output streaming
 */
class PythonInChat private constructor(private val context: Context) {
    
    private val gemini = Gemini2Service.getInstance(context)
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    data class PythonRequest(
        val code: String,
        val description: String? = null,
        val packages: List<String> = emptyList(),
        val timeout: Long = 30000L // 30 seconds default
    )
    
    data class PythonResult(
        val output: String,
        val error: String?,
        val executionTime: Long,
        val success: Boolean,
        val generatedCode: String,
        val explanation: String
    )
    
    companion object {
        @Volatile
        private var instance: PythonInChat? = null
        
        fun getInstance(context: Context): PythonInChat {
            return instance ?: synchronized(this) {
                instance ?: PythonInChat(context.applicationContext).also { instance = it }
            }
        }
    }
    
    /**
     * 🚀 EXECUTE PYTHON CODE
     * Wykonuje kod Python i zwraca wyniki
     */
    suspend fun executePython(
        request: PythonRequest,
        onOutput: (String) -> Unit = {}
    ): PythonResult = withContext(Dispatchers.IO) {
        
        val startTime = System.currentTimeMillis()
        
        try {
            // Check if Python is available
            val pythonPath = findPythonExecutable()
            if (pythonPath == null) {
                return@withContext PythonResult(
                    output = "",
                    error = "Python not found on system",
                    executionTime = 0,
                    success = false,
                    generatedCode = request.code,
                    explanation = "Python interpreter not available"
                )
            }
            
            // Create temp file with code
            val tempFile = createTempPythonFile(request.code)
            
            // Execute Python
            val process = ProcessBuilder(pythonPath, tempFile.absolutePath)
                .redirectErrorStream(true)
                .start()
            
            // Read output in real-time
            val output = StringBuilder()
            val reader = BufferedReader(InputStreamReader(process.inputStream))
            
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                output.appendLine(line)
                onOutput(line!!)
            }
            
            // Wait for completion with timeout
            val completed = withTimeoutOrNull(request.timeout) {
                process.waitFor()
                true
            } ?: false
            
            if (!completed) {
                process.destroy()
                return@withContext PythonResult(
                    output = output.toString(),
                    error = "Execution timeout after ${request.timeout}ms",
                    executionTime = System.currentTimeMillis() - startTime,
                    success = false,
                    generatedCode = request.code,
                    explanation = "Code took too long to execute"
                )
            }
            
            val exitCode = process.exitValue()
            val executionTime = System.currentTimeMillis() - startTime
            
            // Clean up
            tempFile.delete()
            
            PythonResult(
                output = output.toString(),
                error = if (exitCode != 0) "Exit code: $exitCode" else null,
                executionTime = executionTime,
                success = exitCode == 0,
                generatedCode = request.code,
                explanation = request.description ?: "Python code executed"
            )
            
        } catch (e: Exception) {
            PythonResult(
                output = "",
                error = e.message ?: "Unknown error",
                executionTime = System.currentTimeMillis() - startTime,
                success = false,
                generatedCode = request.code,
                explanation = "Error during execution"
            )
        }
    }
    
    /**
     * 🔍 FIND PYTHON EXECUTABLE
     */
    private fun findPythonExecutable(): String? {
        val possiblePaths = listOf(
            "python",
            "python3",
            "python3.11",
            "python3.10",
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "C:\\Python311\\python.exe",
            "C:\\Python310\\python.exe"
        )
        
        for (path in possiblePaths) {
            try {
                val process = ProcessBuilder(path, "--version").start()
                if (process.waitFor() == 0) {
                    return path
                }
            } catch (e: Exception) {
                continue
            }
        }
        
        return null
    }
    
    /**
     * 📝 CREATE TEMP PYTHON FILE
     */
    private fun createTempPythonFile(code: String): java.io.File {
        val tempFile = java.io.File.createTempFile("alfa_python_", ".py")
        tempFile.writeText(code)
        return tempFile
    }
    
    /**
     * 🤖 GENERATE PYTHON CODE FROM NATURAL LANGUAGE
     * AI generuje kod Python na podstawie opisu
     */
    suspend fun generatePythonCode(
        description: String,
        onProgress: (String) -> Unit = {}
    ): String = withContext(Dispatchers.IO) {
        
        onProgress("🤖 Generating Python code...")
        
        val prompt = """
        Generate Python code for this task:
        
        ${description}
        
        Requirements:
        1. Use standard libraries when possible
        2. Include error handling
        3. Add comments explaining key steps
        4. Make it production-ready
        5. Include example usage if applicable
        
        Return ONLY the Python code (no markdown, no explanations).
        """.trimIndent()
        
        val code = gemini.generateText(prompt)
        
        onProgress("✅ Code generated!")
        
        // Clean up markdown if present
        code.replace("```python", "").replace("```", "").trim()
    }
    
    /**
     * 📊 ANALYZE DATA WITH PYTHON
     * Analizuje dane używając Python
     */
    suspend fun analyzeData(
        data: String,
        analysisType: String,
        onOutput: (String) -> Unit = {}
    ): PythonResult {
        
        val pythonCode = """
import json
import statistics

# Parse data
data = json.loads('''$data''')

# Perform analysis: $analysisType
if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
    print(f"Count: {len(data)}")
    print(f"Mean: {statistics.mean(data)}")
    print(f"Median: {statistics.median(data)}")
    print(f"Std Dev: {statistics.stdev(data) if len(data) > 1 else 0}")
    print(f"Min: {min(data)}")
    print(f"Max: {max(data)}")
else:
    print(f"Data type: {type(data)}")
    print(f"Data preview: {str(data)[:200]}")
        """.trimIndent()
        
        return executePython(
            PythonRequest(
                code = pythonCode,
                description = "Data analysis: $analysisType"
            ),
            onOutput = onOutput
        )
    }
    
    /**
     * 🎨 QUICK PYTHON SNIPPETS
     * Predefiniowane snippety Python
     */
    fun getQuickSnippets(): List<PythonSnippet> {
        return listOf(
            PythonSnippet(
                name = "Fetch URL",
                description = "Download content from URL",
                code = """
import requests
url = input("Enter URL: ")
response = requests.get(url)
print(f"Status: {response.status_code}")
print(response.text[:500])
                """.trimIndent()
            ),
            PythonSnippet(
                name = "JSON Parser",
                description = "Parse and format JSON",
                code = """
import json
data = input("Paste JSON: ")
parsed = json.loads(data)
print(json.dumps(parsed, indent=2))
                """.trimIndent()
            ),
            PythonSnippet(
                name = "Calculate Statistics",
                description = "Statistical analysis",
                code = """
import statistics
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
print(f"Mean: {statistics.mean(numbers)}")
print(f"Median: {statistics.median(numbers)}")
print(f"Std Dev: {statistics.stdev(numbers)}")
                """.trimIndent()
            )
        )
    }
    
    data class PythonSnippet(
        val name: String,
        val description: String,
        val code: String
    )
}
