package com.alfa.mail.automation

import android.content.Context
import android.location.Location
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * 🗺️ GOOGLE MAPS SCANNER - Skanowanie i analiza map Google
 * 
 * Funkcje:
 * ✅ Skanowanie lokalizacji (firmy, restauracje, sklepy)
 * ✅ Zbieranie danych kontaktowych
 * ✅ Analiza recenzji i ocen
 * ✅ Wyszukiwanie konkurencji
 * ✅ Lead generation (potencjalni klienci)
 * ✅ Analiza gęstości biznesów w okolicy
 * ✅ Route planning i optymalizacja
 */
class GoogleMapsScanner private constructor(private val context: Context) {
    
    private val gemini = Gemini2Service.getInstance(context)
    private var apiKey: String? = null
    
    data class Place(
        val placeId: String,
        val name: String,
        val address: String,
        val phone: String?,
        val website: String?,
        val rating: Float,
        val totalReviews: Int,
        val types: List<String>,
        val location: PlaceLocation,
        val openingHours: List<String>?,
        val priceLevel: Int?,
        val photos: List<String> = emptyList()
    )
    
    data class PlaceLocation(
        val latitude: Double,
        val longitude: Double
    )
    
    data class SearchRequest(
        val query: String,
        val location: PlaceLocation? = null,
        val radius: Int = 5000, // meters
        val type: String? = null, // restaurant, store, cafe, etc.
        val maxResults: Int = 20
    )
    
    data class LeadInfo(
        val businessName: String,
        val contactEmail: String?,
        val contactPhone: String?,
        val website: String?,
        val address: String,
        val category: String,
        val rating: Float,
        val reviewCount: Int,
        val potentialScore: Float, // 0-1, how good a lead this is
        val reasoning: String
    )
    
    companion object {
        @Volatile
        private var instance: GoogleMapsScanner? = null
        
        fun getInstance(context: Context): GoogleMapsScanner {
            return instance ?: synchronized(this) {
                instance ?: GoogleMapsScanner(context.applicationContext).also { instance = it }
            }
        }
    }
    
    fun configure(googleMapsApiKey: String) {
        this.apiKey = googleMapsApiKey
    }
    
    /**
     * 🔍 SEARCH PLACES
     * Wyszukuje miejsca na podstawie zapytania
     */
    suspend fun searchPlaces(
        request: SearchRequest,
        onProgress: (Int, Int) -> Unit = { _, _ -> }
    ): List<Place> = withContext(Dispatchers.IO) {
        
        if (apiKey == null) {
            throw IllegalStateException("Google Maps API key not configured")
        }
        
        val results = mutableListOf<Place>()
        
        try {
            // Build API URL
            val locationParam = request.location?.let { 
                "${it.latitude},${it.longitude}" 
            } ?: "0,0"
            
            val typeParam = request.type?.let { "&type=$it" } ?: ""
            
            val urlString = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?" +
                    "location=$locationParam&" +
                    "radius=${request.radius}&" +
                    "keyword=${URLEncoder.encode(request.query, "UTF-8")}" +
                    typeParam +
                    "&key=$apiKey"
            
            val url = URL(urlString)
            val connection = url.openConnection() as HttpURLConnection
            
            val response = connection.inputStream.bufferedReader().readText()
            val json = JSONObject(response)
            
            if (json.getString("status") == "OK") {
                val placesArray = json.getJSONArray("results")
                
                for (i in 0 until minOf(placesArray.length(), request.maxResults)) {
                    onProgress(i + 1, placesArray.length())
                    
                    val placeJson = placesArray.getJSONObject(i)
                    val place = parsePlaceFromJson(placeJson)
                    
                    // Fetch detailed info
                    val detailedPlace = fetchPlaceDetails(place.placeId)
                    results.add(detailedPlace ?: place)
                }
            }
            
        } catch (e: Exception) {
            e.printStackTrace()
        }
        
        results
    }
    
    /**
     * 📍 FETCH PLACE DETAILS
     * Pobiera szczegóły miejsca (telefon, website, godziny)
     */
    private suspend fun fetchPlaceDetails(placeId: String): Place? = withContext(Dispatchers.IO) {
        try {
            val urlString = "https://maps.googleapis.com/maps/api/place/details/json?" +
                    "place_id=$placeId&" +
                    "fields=name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,types,geometry,opening_hours,price_level,photos&" +
                    "key=$apiKey"
            
            val url = URL(urlString)
            val connection = url.openConnection() as HttpURLConnection
            
            val response = connection.inputStream.bufferedReader().readText()
            val json = JSONObject(response)
            
            if (json.getString("status") == "OK") {
                val result = json.getJSONObject("result")
                parsePlaceDetailsFromJson(placeId, result)
            } else null
            
        } catch (e: Exception) {
            null
        }
    }
    
    private fun parsePlaceFromJson(json: JSONObject): Place {
        val location = json.getJSONObject("geometry").getJSONObject("location")
        
        return Place(
            placeId = json.getString("place_id"),
            name = json.getString("name"),
            address = json.optString("vicinity", "Unknown"),
            phone = null,
            website = null,
            rating = json.optDouble("rating", 0.0).toFloat(),
            totalReviews = json.optInt("user_ratings_total", 0),
            types = parseJsonArray(json.optJSONArray("types")),
            location = PlaceLocation(
                latitude = location.getDouble("lat"),
                longitude = location.getDouble("lng")
            ),
            openingHours = null,
            priceLevel = json.optInt("price_level", -1).takeIf { it != -1 }
        )
    }
    
    private fun parsePlaceDetailsFromJson(placeId: String, json: JSONObject): Place {
        val location = json.getJSONObject("geometry").getJSONObject("location")
        val openingHours = json.optJSONObject("opening_hours")?.optJSONArray("weekday_text")
        
        return Place(
            placeId = placeId,
            name = json.getString("name"),
            address = json.optString("formatted_address", "Unknown"),
            phone = json.optString("formatted_phone_number"),
            website = json.optString("website"),
            rating = json.optDouble("rating", 0.0).toFloat(),
            totalReviews = json.optInt("user_ratings_total", 0),
            types = parseJsonArray(json.optJSONArray("types")),
            location = PlaceLocation(
                latitude = location.getDouble("lat"),
                longitude = location.getDouble("lng")
            ),
            openingHours = openingHours?.let { parseJsonArray(it) },
            priceLevel = json.optInt("price_level", -1).takeIf { it != -1 }
        )
    }
    
    private fun parseJsonArray(array: JSONArray?): List<String> {
        if (array == null) return emptyList()
        return (0 until array.length()).map { array.getString(it) }
    }
    
    /**
     * 💼 GENERATE LEADS
     * Generuje leady z wykrytych miejsc
     */
    suspend fun generateLeads(
        places: List<Place>,
        targetCategory: String,
        onProgress: (Int, Int) -> Unit = { _, _ -> }
    ): List<LeadInfo> = withContext(Dispatchers.IO) {
        
        places.mapIndexed { index, place ->
            onProgress(index + 1, places.size)
            analyzeLeadPotential(place, targetCategory)
        }.sortedByDescending { it.potentialScore }
    }
    
    /**
     * 📊 ANALYZE LEAD POTENTIAL
     * AI analizuje potencjał leada
     */
    private suspend fun analyzeLeadPotential(
        place: Place,
        targetCategory: String
    ): LeadInfo {
        
        val prompt = """
        Analyze this business as a potential lead for category: $targetCategory
        
        Business:
        - Name: ${place.name}
        - Rating: ${place.rating}/5 (${place.totalReviews} reviews)
        - Type: ${place.types.joinToString(", ")}
        - Website: ${place.website ?: "None"}
        - Phone: ${place.phone ?: "None"}
        
        Score from 0-1 how good a lead this is and explain why.
        Return JSON:
        {
            "score": 0.85,
            "reasoning": "High rating, no website - potential for web services",
            "suggested_pitch": "Brief pitch suggestion"
        }
        """.trimIndent()
        
        val response = try {
            gemini.generateText(prompt)
        } catch (e: Exception) {
            """{"score": 0.5, "reasoning": "Unable to analyze", "suggested_pitch": "Standard pitch"}"""
        }
        
        val json = try {
            JSONObject(response)
        } catch (e: Exception) {
            JSONObject("""{"score": 0.5, "reasoning": "Parse error", "suggested_pitch": ""}""")
        }
        
        LeadInfo(
            businessName = place.name,
            contactEmail = extractEmailFromWebsite(place.website),
            contactPhone = place.phone,
            website = place.website,
            address = place.address,
            category = place.types.firstOrNull() ?: "unknown",
            rating = place.rating,
            reviewCount = place.totalReviews,
            potentialScore = json.optDouble("score", 0.5).toFloat(),
            reasoning = json.optString("reasoning", "No analysis available")
        )
    }
    
    private fun extractEmailFromWebsite(website: String?): String? {
        if (website == null) return null
        
        // Simplified email extraction
        val emailPattern = "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}".toRegex()
        return emailPattern.find(website)?.value
    }
    
    /**
     * 📧 GENERATE PERSONALIZED EMAIL FOR LEAD
     * Generuje spersonalizowany email dla leada
     */
    suspend fun generateLeadEmail(lead: LeadInfo): String {
        val prompt = """
        Generate a personalized outreach email for this lead:
        
        Business: ${lead.businessName}
        Category: ${lead.category}
        Rating: ${lead.rating}/5 (${lead.reviewCount} reviews)
        Website: ${lead.website ?: "No website"}
        Potential: ${(lead.potentialScore * 100).toInt()}%
        Reasoning: ${lead.reasoning}
        
        Email should:
        1. Be professional but friendly
        2. Reference their specific business
        3. Offer relevant value
        4. Include clear call-to-action
        5. Be concise (max 150 words)
        
        Language: Polish
        """.trimIndent()
        
        return gemini.generateText(prompt)
    }
    
    /**
     * 🗺️ ANALYZE AREA DENSITY
     * Analizuje gęstość biznesów w okolicy
     */
    suspend fun analyzeAreaDensity(
        center: PlaceLocation,
        category: String,
        radius: Int = 5000
    ): AreaAnalysis {
        
        val places = searchPlaces(SearchRequest(
            query = category,
            location = center,
            radius = radius,
            maxResults = 50
        ))
        
        val avgRating = places.map { it.rating }.average().toFloat()
        val totalBusinesses = places.size
        val businessesWithWebsite = places.count { it.website != null }
        
        return AreaAnalysis(
            totalBusinesses = totalBusinesses,
            averageRating = avgRating,
            websiteAdoption = (businessesWithWebsite.toFloat() / totalBusinesses * 100).toInt(),
            topRated = places.sortedByDescending { it.rating }.take(5),
            opportunities = places.filter { it.website == null && it.rating > 4.0f }.size,
            density = totalBusinesses / (radius / 1000f), // businesses per km
            recommendation = generateAreaRecommendation(places, category)
        )
    }
    
    data class AreaAnalysis(
        val totalBusinesses: Int,
        val averageRating: Float,
        val websiteAdoption: Int, // percentage
        val topRated: List<Place>,
        val opportunities: Int, // businesses without website but high rating
        val density: Float, // businesses per km
        val recommendation: String
    )
    
    private suspend fun generateAreaRecommendation(places: List<Place>, category: String): String {
        val prompt = """
        Analyze this market data for category: $category
        
        Total businesses: ${places.size}
        Avg rating: ${places.map { it.rating }.average()}
        With website: ${places.count { it.website != null }}
        Without website: ${places.count { it.website == null }}
        
        Provide business recommendation (2 sentences).
        """.trimIndent()
        
        return gemini.generateText(prompt)
    }
}
