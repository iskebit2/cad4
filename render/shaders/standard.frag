// standard.frag
// Ana 3D element fragment shader'ı (Frame, Area, Link, Node).
// MRT: renk (location 0) + pick ID (location 1).
//
// Gölgeleme: ambient + diffuse + specular + rim (fresnel)
// Seçim: VertexColor == SELECTION_COLOR ise sabit turuncu

#version 460 core

// ---- Vertex'ten gelen ----
in vec3      FragPos;
in vec3      Normal;
in vec3      VertexColor;
flat in uint vID;

// ---- MRT output ----
layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

// ---- Sabitler ----
const vec3 SELECTION_COLOR = vec3(1.0, 0.5, 0.0);
const float SELECTION_EPS  = 0.05;
#define MAX_LIGHTS 8

// ---- Uniform'lar ----
uniform bool  useVertexColor;
uniform vec3  objectColor;
uniform float alpha;
uniform int   renderMode;      // 0 = normal debug, 1 = shaded

layout(std140, binding = 0) uniform LightData {
    int   lightCount;
    float pad1, pad2, pad3;

    vec4  lightPositions[MAX_LIGHTS];
    vec4  lightColors[MAX_LIGHTS];

    vec4  viewPos;

    float ambientStrength;
    float diffuseStrength;
    float specularStrength;
    float shininess;
    float globalBrightness;
} lights;

uniform float rimPower;
uniform float rimIntensity;

// ------------------------------------------------------------
// YARDIMCILAR
// ------------------------------------------------------------
bool is_selected_color(vec3 c) {
    return abs(c.r - SELECTION_COLOR.r) < SELECTION_EPS &&
           abs(c.g - SELECTION_COLOR.g) < SELECTION_EPS &&
           abs(c.b - SELECTION_COLOR.b) < SELECTION_EPS;
}

vec3 tonemap(vec3 c) {
    // Reinhard + gamma
    c = c / (c + vec3(1.0));
    return pow(max(c, vec3(0.0)), vec3(1.0 / 2.2));
}

// ------------------------------------------------------------
// MAIN
// ------------------------------------------------------------
void main() {
    vec3 norm     = normalize(Normal);
    bool selected = is_selected_color(VertexColor);

    // --- Base renk ---
    vec3 baseColor;
    if (selected) {
        baseColor = SELECTION_COLOR;
    } else if (renderMode == 0) {
        // Normal debug
        baseColor = norm * 0.5 + 0.5;
        FragColor = vec4(baseColor, alpha);
        FragID    = vID;
        return;
    } else {
        baseColor = useVertexColor ? VertexColor : objectColor;
    }

    // --- Işıklandırma ---
    vec3 color = baseColor * lights.ambientStrength;

    int numLights = clamp(lights.lightCount, 0, MAX_LIGHTS);
    for (int i = 0; i < numLights; i++) {
        vec3 lightDir   = normalize(lights.lightPositions[i].xyz);
        vec3 lightColor = lights.lightColors[i].xyz;

        float NdotL = max(dot(norm, lightDir), 0.0);

        // Diffuse
        color += baseColor * lightColor * NdotL * lights.diffuseStrength;

        // Specular
        if (lights.specularStrength > 0.0 && NdotL > 0.0) {
            vec3 viewDir    = normalize(lights.viewPos.xyz - FragPos);
            vec3 halfwayDir = normalize(lightDir + viewDir);
            float NdotH     = max(dot(norm, halfwayDir), 0.0);
            float spec      = pow(NdotH, max(lights.shininess, 1.0));
            color += lightColor * spec * lights.specularStrength;
        }
    }

    // --- Rim (fresnel) ---
    if (rimIntensity > 0.0) {
        vec3 viewDir = normalize(lights.viewPos.xyz - FragPos);
        float NdotV  = max(dot(norm, viewDir), 0.0);
        float fresnel = pow(1.0 - NdotV, max(rimPower, 1.0));
        color += baseColor * fresnel * rimIntensity;
    }

    // --- Brightness + tonemap + gamma ---
    color = tonemap(color * lights.globalBrightness);

    FragColor = vec4(color, alpha);
    FragID    = vID;
}