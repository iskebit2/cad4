// node.frag
// Node nokta fragment shader'ı.
// MRT: color (location 0) + pick ID (location 1).
//
// Filtreleme:
//   - Eleman düzeyi: CPU `visible_ids`.
//   - CLIP: burada fragment `discard`.

#version 460 core

in vec3      VertexColor;
in vec3      v_world_pos;
flat in uint vID;

layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

uniform bool  useVertexColor;
uniform vec3  objectColor;
uniform float alpha;

// ---- CLIP uniform'ları ----
uniform bool  u_clip_active;
uniform vec3  u_plane_origin;
uniform vec3  u_plane_normal;
uniform vec3  u_plane_u;
uniform vec3  u_plane_v;
uniform float u_u_min, u_u_max;
uniform float u_v_min, u_v_max;
uniform float u_depth_minus, u_depth_plus;

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

void main() {
    if (clip_discard()) {
        discard;
    }
    vec3 color = useVertexColor ? VertexColor : objectColor;
    FragColor = vec4(color, alpha);
    FragID    = vID;
}