// Shared filtering; all projects/chats come from the same owner APIs.
export function conversationGroups(projects,chats){
 const active=chats.filter(chat=>!chat.archived&&!chat.removed&&!chat.validation_archive);
 return [...projects.filter(project=>!project.removed&&!project.validation_archive).map(project=>({
  id:project.id,title:project.name,path:project.path,project,
  chats:active.filter(chat=>chat.project_id===project.id)
 })),{id:'$independent',title:'独立会话',path:'',chats:active.filter(chat=>!chat.project_id)}];
}
