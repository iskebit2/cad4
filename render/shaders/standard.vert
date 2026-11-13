// standard.vert
#version 460 core

layout(location = 0) in vec3  aPos;
layout(location = 1) in vec3  aNormal;
layout(location = 2) in vec3  aColor;
layout(location = 3) in uint  aPickId;

out vec3      FragPos;
flat out vec3 Normal;
out vec3      VertexColor;
out vec3      v_world_pos;
flat out uint vID;

uniform mat4 mvp;
uniform mat4 model;
uniform mat3 normalMatrix;

void main() {
    vec4 world  = model * vec4(aPos, 1.0);
    v_world_pos = world.xyz;
    FragPos     = world.xyz;
    Normal      = normalize(normalMatrix * aNormal);
    VertexColor = aColor;
    vID         = aPickId;
    gl_Position = mvp * vec4(aPos, 1.0);
}