package delivery

type SSENetworkReq struct {
	Ticket string `form:"ticket" binding:"required,uuid"`
	LastID string `header:"Last-Event-ID"`
}
