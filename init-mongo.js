rsconf = {
    _id: "rs0",
    members: [
        {
            _id: 0, 
            host: "127.0.0.1:27027",
            priority: 1
        },
    ]
};

rs.initiate(rsconf,{"force":true})