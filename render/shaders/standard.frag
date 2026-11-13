// standard.frag
// Ana 3D element fragment shader'ı.
// MRT: color (location 0) + pick ID (location 1).
//
// Filtreleme sorumlulukları:
//   - Eleman düzeyi (tip, INTERSECT, STRICT): CPU `visible_ids` hallediyor.
//     Shader yalnızca o elemanlar için draw call alır; burada tekrar filtre YOK.
//   - CLIP: burada fragment `discard` ile gerçek kesme uygulanır.
//
// Gölgeleme: ambient + diffuse + specular + rim (fresnel).
// Seçim: VertexColor == SELECTION_COLOR ise sabit turuncu.

#version 460 core

// ---- Vertex'ten gelen ----
in vec3      FragPos;
flat in vec3 Normal;
in vec3      VertexColor;
in vec3      v_world_pos;

// ---- MRT output ----
layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

// ---- Sabitler ----
const vec3  SELECTION_COLOR = vec3(1.0, 0.5, 0.0);
const float SELECTION_EPS   = 0.05;
#define MAX_LIGHTS 8

// ---- Temel uniform'lar ----
uniform bool  useVertexColor;
uniform vec3  objectColor;
uniform float alpha;
uniform int   renderMode;      // 0 = debug, 1 = shaded
uniform uint  vID;

// ---- CLIP uniform'ları ----
uniform bool  u_clip_active;
uniform vec3  u_plane_origin;
uniform vec3  u_plane_normal;
uniform vec3  u_plane_u;
uniform vec3  u_plane_v;
uniform float u_u_min, u_u_max;
uniform float u_v_min, u_v_max;
uniform float u_depth_minus, u_depth_plus;

// ---- Işık UBO ----
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
// Yardımcılar
// ------------------------------------------------------------
bool is_selected_color(vec3 c) {
    return abs(c.r - SELECTION_COLOR.r) < SELECTION_EPS &&
           abs(c.g - SELECTION_COLOR.g) < SELECTION_EPS &&
           abs(c.b - SELECTION_COLOR.b) < SELECTION_EPS;
}

vec3 tonemap(vec3 c) {
    c = c / (c + vec3(1.0));
    return pow(max(c, vec3(0.0)), vec3(1.0 / 2.2));
}

// ------------------------------------------------------------
// CLIP — yalnızca düzlem kesme uygulanır
// ------------------------------------------------------------
bool clip_discard() {
    if (!u_clip_active) {
        return false;
    }
    vec3 rel = v_world_pos - u_plane_origin;
    float d = dot(rel, u_plane_normal);
    if (d < -u_depth_minus || d > u_depth_plus) {
        return true;
    }
    float u = dot(rel, u_plane_u);
    float v = dot(rel, u_plane_v);
    if (u < u_u_min || u > u_u_max || v < u_v_min || v > u_v_max) {
        return true;
    }
    return false;
}

// ------------------------------------------------------------
// Shading
// ------------------------------------------------------------
vec3 shade(vec3 baseColor, vec3 norm, bool selected) {
    if (selected || renderMode == 0) {
        return baseColor;
    }

    vec3 color = baseColor * lights.ambientStrength;
    int numLights = clamp(lights.lightCount, 0, MAX_LIGHTS);

    for (int i = 0; i < numLights; ++i) {
        vec3  lightDir   = normalize(lights.lightPositions[i].xyz);
        vec3  lightColor = lights.lightColors[i].xyz;
        float NdotL      = max(dot(norm, lightDir), 0.0);

        color += baseColor * lightColor * NdotL * lights.diffuseStrength;

        if (lights.specularStrength > 0.0 && NdotL > 0.0) {
            vec3  viewDir    = normalize(lights.viewPos.xyz - FragPos);
            vec3  halfwayDir = normalize(lightDir + viewDir);
            float NdotH      = max(dot(norm, halfwayDir), 0.0);
            float spec       = pow(NdotH, max(lights.shininess, 1.0));
            color += lightColor * spec * lights.specularStrength;
        }
    }

    if (rimIntensity > 0.0) {
        vec3  viewDir  = normalize(lights.viewPos.xyz - FragPos);
        float NdotV    = max(dot(norm, viewDir), 0.0);
        float fresnel  = pow(1.0 - NdotV, max(rimPower, 1.0));
        color += baseColor * fresnel * rimIntensity;
    }

    return tonemap(color * lights.globalBrightness);
}

// ------------------------------------------------------------
// Main
// ------------------------------------------------------------
void main() {
    if (clip_discard()) {
        discard;
    }

    vec3 norm     = normalize(Normal);
    bool selected = is_selected_color(VertexColor);

    vec3 baseColor;
    if (selected) {
        baseColor = SELECTION_COLOR;
    } else if (renderMode == 0) {
        baseColor = norm * 0.5 + 0.5;
        FragColor = vec4(baseColor, alpha);
        FragID    = vID;
        return;
    } else {
        baseColor = useVertexColor ? VertexColor : objectColor;
    }

    vec3 color = shade(baseColor, norm, selected);

    FragColor = vec4(color, alpha);
    FragID    = vID;
}