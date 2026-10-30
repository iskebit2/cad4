#version 460 core
in vec3 VertexColor;
flat in uint VertexPickId;
flat in float PlaneOpacity;

layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

void main() {
    FragColor = vec4(VertexColor, PlaneOpacity);
    FragID = VertexPickId;
}