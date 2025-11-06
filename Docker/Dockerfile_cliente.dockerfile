FROM eclipse-temurin:21-jdk as build
WORKDIR /workspace
# copy java client pom and src from req-rep/java-client
COPY ./req-rep/java-client/pom.xml ./pom.xml
COPY ./req-rep/java-client/src ./src
RUN apt-get update && apt-get install -y maven && mvn -v
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /workspace/target/app-jar-with-dependencies.jar ./app.jar
EXPOSE 0
ENTRYPOINT ["java","-jar","/app/app.jar"]
