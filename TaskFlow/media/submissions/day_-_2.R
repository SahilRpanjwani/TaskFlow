	Sys.setenv(http_proxy="http://192.168.10.253:808")
	Sys.setenv(https_proxy="http://192.168.10.253:808")
a<-read.csv("Z://dm//student.csv")
a
data <- datasets::iris
view(data)

select(da,Sepal.Length)
select(da,Sepal.Length,3)
select(da,1,Petal.Length)
View(data)

head(select(da,1,Petal.Length))
tail(select(da,1,Petal.Length))
tail(select(da,1,Petal.Length),2)

select(data,1:4)
select(data,-Species)

arrange(data,Sepal.Length)
arrange(data,desc(data))
arrange(data,desc(Petal.Length))





