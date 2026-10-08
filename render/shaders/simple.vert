#version 460 core

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;      // ← CBO'dan gelecek
layout(location = 3) in uint aObjectID;

out vec3 VertexColor;
flat out uint ObjectID;

uniform mat4 mvp;

void main() {
    gl_Position = mvp * vec4(aPos, 1.0);
    VertexColor = aColor;      // ← doğrudan kullan
    ObjectID = aObjectID;
    gl_PointSize = 6.0;
}