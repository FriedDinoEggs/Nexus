package domain

import "slices"

type Identity struct {
	UserID  int64
	GroupID []int64
}

type Role int

const (
	RoleAdmin Role = iota
	RoleEventManager
	RoleMember
	RoleUndefined
)

func (a Identity) IsAdmin() bool   { return slices.Contains(a.GroupID, 1) }
func (a Identity) IsManager() bool { return slices.Contains(a.GroupID, 2) }
func (a Identity) IsMember() bool  { return slices.Contains(a.GroupID, 3) }

func (a Identity) FetchRole() []Role {
	var roleList []Role
	if a.IsAdmin() {
		roleList = append(roleList, RoleAdmin)
	}
	if a.IsManager() {
		roleList = append(roleList, RoleEventManager)
	}
	if a.IsMember() {
		roleList = append(roleList, RoleMember)
	}
	if len(roleList) == 0 {
		roleList = append(roleList, RoleUndefined)
	}
	return roleList
}
