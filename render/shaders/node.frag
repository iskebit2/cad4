#version 460 core
in vec3 VertexColor;
flat in uint VertexPickId;

layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

void main() {
    FragColor = vec4(VertexColor, 1.0);
    FragID = VertexPickId;
}